#!/bin/bash

# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Script to generate a factory install partition set and miniomaha.conf
# file from a release image and a factory image. This creates a server
# configuration that can be installed using a factory install shim.
#
# miniomaha lives in src/platform/dev/ and miniomaha partition sets live
# in src/platform/dev/static.

# --- BEGIN COMMON.SH BOILERPLATE ---
# Load common CrOS utilities.  Inside the chroot this file is installed in
# /usr/lib/crosutils.  Outside the chroot we find it relative to the script's
# location.
find_common_sh() {
  local common_paths=(/usr/lib/crosutils $(dirname "$(readlink -f "$0")"))
  local path

  SCRIPT_ROOT=
  for path in "${common_paths[@]}"; do
    if [ -r "${path}/common.sh" ]; then
      SCRIPT_ROOT=${path}
      break
    fi
  done
}

find_common_sh
. "${SCRIPT_ROOT}/common.sh" || (echo "Unable to load common.sh" && exit 1)
# --- END COMMON.SH BOILERPLATE ---

# Need to be inside the chroot to load chromeos-common.sh
assert_inside_chroot

# Load functions and constants for chromeos-install
. "/usr/lib/installer/chromeos-common.sh" || \
  die "Unable to load /usr/lib/installer/chromeos-common.sh"

# Load functions designed for image processing
. "${SCRIPT_ROOT}/lib/cros_image_common.sh" ||
  die "Cannot load required library: lib/cros_image_common.sh; Abort."

get_default_board

# Flags
DEFINE_string board "${DEFAULT_BOARD}" "Board for which the image was built"
DEFINE_string factory "" \
  "Directory and file containing factory image: /path/chromiumos_test_image.bin"
DEFINE_string firmware_updater "" \
  "If set, include the firmware shellball into the server configuration"
DEFINE_string release "" \
  "Directory and file containing release image: /path/chromiumos_image.bin"
DEFINE_string subfolder "" \
  "If set, the name of the subfolder to put the payload items inside"
DEFINE_string diskimg "" \
  "If set, the name of the diskimage file to output"
DEFINE_boolean preserve ${FLAGS_FALSE} \
  "If set, reuse the diskimage file, if available"
DEFINE_integer sectors 31277232  "Size of image in sectors"

# Parse command line
FLAGS "$@" || exit 1
eval set -- "${FLAGS_ARGV}"

if [ ! -f "${FLAGS_release}" ]; then
  echo "Cannot find image file ${FLAGS_release}"
  exit 1
fi

if [ ! -f "${FLAGS_factory}" ]; then
  echo "Cannot find image file ${FLAGS_factory}"
  exit 1
fi

if [ -n "${FLAGS_firmware_updater}" ] &&
   [ ! -f "${FLAGS_firmware_updater}" ]; then
  echo "Cannot find firmware file ${FLAGS_firmware_updater}"
  exit 1
fi

# Convert args to paths.  Need eval to un-quote the string so that shell
# chars like ~ are processed; just doing FOO=`readlink -f ${FOO}` won't work.
OMAHA_DIR="${SRC_ROOT}/platform/dev"
OMAHA_CONF="${OMAHA_DIR}/miniomaha.conf"
OMAHA_DATA_DIR="${OMAHA_DIR}/static/"

# Note: The subfolder flag can only append configs.  That means you will need
# to have unique board IDs for every time you run.  If you delete miniomaha.conf
# you can still use this flag and it will start fresh.
if [ -n "${FLAGS_subfolder}" ]; then
  OMAHA_DATA_DIR="${OMAHA_DIR}/static/${FLAGS_subfolder}/"
fi

if [ ${INSIDE_CHROOT} -eq 0 ]; then
  echo "Caching sudo authentication"
  sudo -v
  echo "Done"
fi

# Use this image as the source image to copy
RELEASE_DIR="$(dirname "${FLAGS_release}")"
FACTORY_DIR="$(dirname "${FLAGS_factory}")"
RELEASE_IMAGE="$(basename "${FLAGS_release}")"
FACTORY_IMAGE="$(basename "${FLAGS_factory}")"

prepare_img() {
  local outdev="$(readlink -f "$FLAGS_diskimg")"
  local sectors="$FLAGS_sectors"
  local force_full="true"

  # We'll need some code to put in the PMBR, for booting on legacy BIOS.
  echo "Fetch PMBR"
  local pmbrcode="$(mktemp -d)/gptmbr.bin"
  sudo dd bs=512 count=1 if="${FLAGS_release}" of="${pmbrcode}" status=noxfer

  echo "Prepare base disk image"
  # Create an output file if requested, or if none exists.
  if [ -b "${outdev}" ] ; then
    echo "Using block device ${outdev}"
  elif [ ! -e "${outdev}" -o \
        "$(stat -c %s ${outdev})" != "$(( ${sectors} * 512 ))"  -o \
        "$FLAGS_preserve" = "$FLAGS_FALSE" ]; then
    echo "Generating empty image file"
    image_dump_partial_file /dev/zero 0 "${sectors}" |
        dd of="${outdev}" bs=8M
  else
    echo "Reusing $outdev"
  fi

  # Create GPT partition table.
  locate_gpt
  install_gpt "${outdev}" 0 0 "${pmbrcode}" 0 "${force_full}"
  # Activate the correct partition.
  sudo "${GPT}" add -i 2 -S 1 -P 1 "${outdev}"
}

prepare_omaha() {
  sudo rm -rf "${OMAHA_DATA_DIR}/rootfs-test.gz"
  sudo rm -rf "${OMAHA_DATA_DIR}/rootfs-release.gz"
  rm -rf "${OMAHA_DATA_DIR}/efi.gz"
  rm -rf "${OMAHA_DATA_DIR}/oem.gz"
  rm -rf "${OMAHA_DATA_DIR}/state.gz"
  if [ ! -d "${OMAHA_DATA_DIR}" ]; then
    mkdir -p "${OMAHA_DATA_DIR}"
  fi
}

prepare_dir() {
  sudo rm -rf rootfs-test.gz
  sudo rm -rf rootfs-release.gz
  rm -rf efi.gz
  rm -rf oem.gz
  rm -rf state.gz
}

compress_and_hash_memento_image() {
  local input_file="$1"

  if [ -n "${IMAGE_IS_UNPACKED}" ]; then
    sudo "${SCRIPTS_DIR}/mk_memento_images_factory.sh" part_2 part_3 |
      grep hash |
      awk '{print $4}'
  else
    sudo "${SCRIPTS_DIR}/mk_memento_images_factory.sh" "$input_file" 2 3 |
      grep hash |
      awk '{print $4}'
  fi
}

compress_and_hash_file() {
  local input_file="$1"
  local output_file="$2"

  if [ -z "$input_file" ]; then
    # Runs as a pipe processor
    image_gzip_compress -c -9 |
    tee "$output_file" |
    openssl sha1 -binary |
    openssl base64
  else
    image_gzip_compress -c -9 "$input_file" |
    tee "$output_file" |
    openssl sha1 -binary |
    openssl base64
  fi
}

compress_and_hash_partition() {
  local input_file="$1"
  local part_num="$2"
  local output_file="$3"

  if [ -n "${IMAGE_IS_UNPACKED}" ]; then
    compress_and_hash_file "part_$part_num" "$output_file"
  else
    image_dump_partition "$input_file" "$part_num" |
    compress_and_hash_file "" "$output_file"
  fi
}

# Decide if we should unpack partition
if image_has_part_tools; then
  IMAGE_IS_UNPACKED=
else
  #TODO(hungte) Currently we run unpack_partitions.sh if part_tools are not
  # found. If the format of unpack_partitions.sh is reliable, we can prevent
  # creating temporary files. See image_part_offset for more information.
  echo "WARNING: cannot find partition tools. Using unpack_partitions.sh." >&2
  IMAGE_IS_UNPACKED=1
fi

mount_esp() {
  local image="$1"
  local esp_mountpoint="$2"
  offset=$(partoffset "${image}" 12)
  sudo mount -o loop,offset=$(( offset * 512 )) \
      "${image}" "${esp_mountpoint}"
  ESP_MOUNT="${esp_mountpoint}"
}

umount_esp() {
  if [ -n "${ESP_MOUNT}" ]; then
    sudo umount "${ESP_MOUNT}"
  fi
}

generate_img() {
  local outdev="$(readlink -f "$FLAGS_diskimg")"
  local sectors="$FLAGS_sectors"

  prepare_img

  # Get the release image.
  pushd "${RELEASE_DIR}" >/dev/null

  echo "Release Kernel"
  image_partition_copy "${RELEASE_IMAGE}" 2 "${outdev}" 4
  echo "Release Rootfs"
  image_partition_copy "${RELEASE_IMAGE}" 3 "${outdev}" 5
  echo "OEM parition"
  image_partition_copy "${RELEASE_IMAGE}" 8 "${outdev}" 8

  popd >/dev/null

  # Go to retrieve the factory test image.
  pushd "${FACTORY_DIR}" >/dev/null

  echo "Factory Kernel"
  image_partition_copy "${FACTORY_IMAGE}" 2 "${outdev}" 2
  echo "Factory Rootfs"
  image_partition_copy "${FACTORY_IMAGE}" 3 "${outdev}" 3
  echo "Factory Stateful"
  image_partition_copy "${FACTORY_IMAGE}" 1 "${outdev}" 1
  echo "EFI Partition"
  image_partition_copy "${FACTORY_IMAGE}" 12 "${outdev}" 12

  # TODO(nsanders, wad): consolidate this code into some common code
  # when cleaning up kernel commandlines. There is code that touches
  # this in postint/chromeos-setimage and build_image. However none
  # of the preexisting code actually does what we want here.
  local tmpesp="$(mktemp -d)"
  mount_esp "${outdev}" "${tmpesp}"

  trap "umount_esp" EXIT

  # Edit boot device default for legacy.
  # Support both vboot and regular boot.
  sudo sed -i "s/chromeos-usb.A/chromeos-hd.A/" \
      "${tmpesp}"/syslinux/default.cfg
  sudo sed -i "s/chromeos-vusb.A/chromeos-vhd.A/" \
      "${tmpesp}"/syslinux/default.cfg

  # Edit root fs default for legacy
  # Somewhat safe as ARM does not support syslinux, I believe.
  sudo sed -i "s'HDROOTA'/dev/sda3'g" "${tmpesp}"/syslinux/root.A.cfg

  trap - EXIT

  umount_esp

  echo "Generated Image at $outdev."
  echo "Done"
}

generate_omaha() {
  # Clean up stale config and data files.
  prepare_omaha

  # Get the release image.
  pushd "${RELEASE_DIR}" >/dev/null
  echo "Generating omaha release image from ${FLAGS_release}"
  echo "Generating omaha factory image from ${FLAGS_factory}"
  echo "Output omaha image to ${OMAHA_DATA_DIR}"
  echo "Output omaha config to ${OMAHA_CONF}"

  prepare_dir

  if [ -n "${IMAGE_IS_UNPACKED}" ]; then
    echo "Unpacking image ${RELEASE_IMAGE} ..." >&2
    sudo ./unpack_partitions.sh "${RELEASE_IMAGE}" 2>/dev/null
  fi

  release_hash="$(compress_and_hash_memento_image "${RELEASE_IMAGE}")"
  sudo chmod a+rw update.gz
  mv update.gz rootfs-release.gz
  mv rootfs-release.gz "${OMAHA_DATA_DIR}"
  echo "release: ${release_hash}"

  oem_hash="$(compress_and_hash_partition "${RELEASE_IMAGE}" 8 "oem.gz")"
  mv oem.gz "${OMAHA_DATA_DIR}"
  echo "oem: ${oem_hash}"

  popd >/dev/null

  # Go to retrieve the factory test image.
  pushd "${FACTORY_DIR}" >/dev/null
  prepare_dir

  if [ -n "${IMAGE_IS_UNPACKED}" ]; then
    echo "Unpacking image ${FACTORY_IMAGE} ..." >&2
    sudo ./unpack_partitions.sh "${FACTORY_IMAGE}" 2>/dev/null
  fi

  test_hash="$(compress_and_hash_memento_image "${FACTORY_IMAGE}")"
  sudo chmod a+rw update.gz
  mv update.gz rootfs-test.gz
  mv rootfs-test.gz "${OMAHA_DATA_DIR}"
  echo "test: ${test_hash}"

  state_hash="$(compress_and_hash_partition "${FACTORY_IMAGE}" 1 "state.gz")"
  mv state.gz "${OMAHA_DATA_DIR}"
  echo "state: ${state_hash}"

  efi_hash="$(compress_and_hash_partition "${FACTORY_IMAGE}" 12 "efi.gz")"
  mv efi.gz "${OMAHA_DATA_DIR}"
  echo "efi: ${efi_hash}"

  popd >/dev/null

  if [ -n "${FLAGS_firmware_updater}" ]; then
    SHELLBALL="${FLAGS_firmware_updater}"
    if [ ! -f  "$SHELLBALL" ]; then
      echo "Failed to find firmware updater: $SHELLBALL."
      exit 1
    fi

    firmware_hash="$(compress_and_hash_file "$SHELLBALL" "firmware.gz")"
    mv firmware.gz "${OMAHA_DATA_DIR}"
    echo "firmware: ${firmware_hash}"
  fi

  # If the file does exist and we are using the subfolder flag we are going to
  # append another config.
  if [ -n "${FLAGS_subfolder}" ] &&
     [ -f "${OMAHA_CONF}" ]; then
    # Remove the ']' from the last line of the file
    # so we can add another config.
    while  [ -s "${OMAHA_CONF}" ]; do
      # If the last line is null
      if [ -z "$(tail -1 "${OMAHA_CONF}")" ]; then
        sed -i '$d' "${OMAHA_CONF}"
      elif [ "$(tail -1 "${OMAHA_CONF}")" != ']' ]; then
        sed -i '$d' "${OMAHA_CONF}"
      else
        break
      fi
    done

    # Remove the last ]
    if [ "$(tail -1 "${OMAHA_CONF}")" = ']' ]; then
      sed -i '$d' "${OMAHA_CONF}"
    fi

    # If the file is empty, create it from scratch
    if [ ! -s "${OMAHA_CONF}" ]; then
      echo "config = [" >"${OMAHA_CONF}"
    fi
  else
    echo "config = [" >"${OMAHA_CONF}"
  fi

  if [ -n "${FLAGS_subfolder}" ]; then
    subfolder="${FLAGS_subfolder}/"
  fi

  echo -n "{
   'qual_ids': set([\"${FLAGS_board}\"]),
   'factory_image': '${subfolder}rootfs-test.gz',
   'factory_checksum': '${test_hash}',
   'release_image': '${subfolder}rootfs-release.gz',
   'release_checksum': '${release_hash}',
   'oempartitionimg_image': '${subfolder}oem.gz',
   'oempartitionimg_checksum': '${oem_hash}',
   'efipartitionimg_image': '${subfolder}efi.gz',
   'efipartitionimg_checksum': '${efi_hash}',
   'stateimg_image': '${subfolder}state.gz',
   'stateimg_checksum': '${state_hash}'," >>"${OMAHA_CONF}"

  if [ -n "${FLAGS_firmware_updater}" ]  ; then
    echo -n "
   'firmware_image': '${subfolder}firmware.gz',
   'firmware_checksum': '${firmware_hash}'," >>"${OMAHA_CONF}"
  fi

  echo -n "
 },
]
" >>"${OMAHA_CONF}"

  echo "The miniomaha server lives in src/platform/dev.
To validate the configutarion, run:
  python2.6 devserver.py --factory_config miniomaha.conf \
  --validate_factory_config
To run the server:
  python2.6 devserver.py --factory_config miniomaha.conf"
}

# Main
if [ -n "$FLAGS_diskimg" ]; then
  generate_img
else
  generate_omaha
fi
