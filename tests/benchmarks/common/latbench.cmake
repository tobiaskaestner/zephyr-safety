# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

# Adds the common latency benchmark code to the app target.

target_include_directories(app PRIVATE ${CMAKE_CURRENT_LIST_DIR}/include)
if(CONFIG_LATBENCH_CODE_RAM)
  # The code pad goes to a library of its own (latbench_code_ram() below).
  target_sources(app PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/src/hist.c
    ${CMAKE_CURRENT_LIST_DIR}/src/meta.c
  )
else()
  # pad.c is first: its code comes before all other app and kernel code.
  # Keep this list and its order: they set the code layout in flash.
  target_sources(app PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/src/pad.c
    ${CMAKE_CURRENT_LIST_DIR}/src/hist.c
    ${CMAKE_CURRENT_LIST_DIR}/src/meta.c
  )
endif()

# Put the rev of the benchmark sources into the output, so that each log
# names the code that produced it. run.py passes LATBENCH_SRC_REV, because
# it builds from a snapshot without .git. A manual build asks git; a dirty
# tree gets "-dirty".
if(NOT DEFINED LATBENCH_SRC_REV)
  execute_process(
    COMMAND git describe --always --abbrev=12 --dirty
    WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
    OUTPUT_VARIABLE LATBENCH_SRC_REV
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
endif()
if(NOT LATBENCH_SRC_REV)
  set(LATBENCH_SRC_REV unknown)
endif()
target_compile_definitions(app PRIVATE LATBENCH_SRC_REV="${LATBENCH_SRC_REV}")

# The hardware stimulus (common/src/stim.c) needs the board port that
# common/latbench_board.cmake selected. An app that uses it sets
# LATBENCH_STIM before the include.
if(LATBENCH_STIM)
  if(NOT LATBENCH_PORT_DIR)
    message(FATAL_ERROR "latbench: include common/latbench_board.cmake before find_package(Zephyr)")
  endif()
  target_include_directories(app PRIVATE ${LATBENCH_PORT_DIR}/include)
  target_sources(app PRIVATE
    ${LATBENCH_PORT_DIR}/port.c
    ${CMAKE_CURRENT_LIST_DIR}/src/stim.c
    # The load timers take their tick period from the stimulus.
    ${CMAKE_CURRENT_LIST_DIR}/src/load.c
  )
endif()

# Hot code in RAM (LATBENCH_CODE_RAM in common/Kconfig). Relocates the code
# of the hot paths with zephyr_code_relocate(). Facts about Zephyr's
# relocation (gen_relocate_app.py) that this code depends on:
#
# - It sorts the input sections of a region by the base name of the object
#   file. The pad must come first, so it is compiled from a wrapper file
#   "0_latbench_pad.c" in a library of its own.
# - It skips a file without an error if it does not find its object.
# - For the default RAM region ("RAM") it puts the .bss and .noinit
#   sections of a relocated file into the .data output section. For
#   kernel/init.c this includes z_interrupt_stacks, the stack that
#   arch_data_copy() runs on: the copy overwrites its own return address,
#   and the board locks up at boot. Thus only code and read-only data are
#   relocated (LOCATION <region>_TEXT_RODATA).
#
# A linker check stops the build if the pad is not the first relocated
# function, or if one function of each relocated group is not in the
# relocated code.

# Relocate the sources of library lib, without the files whose name matches
# the regular expression exclude (empty: none).
function(latbench_relocate_lib lib loc exclude)
  if(NOT TARGET ${lib})
    message(FATAL_ERROR "latbench: LATBENCH_CODE_RAM: no library ${lib} in this tree")
  endif()
  get_target_property(dir ${lib} SOURCE_DIR)
  get_target_property(srcs ${lib} SOURCES)
  set(files)
  foreach(src ${srcs})
    get_filename_component(name ${src} NAME)
    if(exclude STREQUAL "" OR NOT name MATCHES "${exclude}")
      get_filename_component(src ${src} ABSOLUTE BASE_DIR ${dir})
      list(APPEND files ${src})
    endif()
  endforeach()
  if(files)
    zephyr_code_relocate(FILES ${files} LOCATION ${loc} NOKEEP)
  endif()
endfunction()

function(latbench_code_ram)
  set(region "${CONFIG_LATBENCH_CODE_RAM_REGION}")
  if(region STREQUAL "")
    message(FATAL_ERROR "latbench: LATBENCH_CODE_RAM: the board port ${LATBENCH_BOARD} gives no RAM "
      "region. Set LATBENCH_CODE_RAM_REGION in common/boards/${LATBENCH_BOARD}/Kconfig.port, "
      "or use LATBENCH_CODE_FLASH or LATBENCH_CODE_FLASH_PAD.")
  endif()
  if(NOT region STREQUAL "RAM" AND NOT LATBENCH_CODE_RAM_PORT_REGION STREQUAL region)
    message(FATAL_ERROR "latbench: LATBENCH_CODE_RAM_REGION=${region}: the board port did not add "
      "this memory region. Set CONFIG_LATBENCH_CODE_RAM=y on the cmake command line (the port "
      "adds its overlay before Kconfig runs).")
  endif()
  string(TOLOWER "${region}" mem)
  set(loc ${region}_TEXT_RODATA)

  # Files that run, or are read, before arch_data_copy() copies the
  # relocated code: the reset code, z_prep_c() and the vector table.
  set(boot "^(reset\\.S|prep_c\\.c|vector_table\\.S)$")
  # z_arm_mpu_init() enables the MPU with the "SRAM_0" region, which is
  # execute-never. CODE_DATA_RELOCATION_SRAM adds the executable region of
  # the relocated code only later, in z_arm_configure_static_mpu_regions().
  # The code that runs between the two calls (z_cstart() in kernel/init.c
  # and the MPU driver) must stay in flash, or it faults
  # (K_ERR_ARM_MEM_INSTRUCTION_ACCESS).
  set(kernel_exclude "")
  set(mpu_lib arch__arm__core__mpu)
  if(region STREQUAL "RAM" AND CONFIG_ARM_MPU)
    set(kernel_exclude "^init\\.c$")
    set(mpu_lib "")
  endif()

  set(pad_src ${CMAKE_CURRENT_BINARY_DIR}/latbench/0_latbench_pad.c)
  file(WRITE ${pad_src} "/* Generated by common/latbench.cmake */\n#include \"${CMAKE_CURRENT_FUNCTION_LIST_DIR}/src/pad.c\"\n")
  add_library(latbench_pad STATIC ${pad_src})
  target_link_libraries(latbench_pad PRIVATE zephyr_interface)
  # As a Zephyr library: build it after the generated headers.
  add_dependencies(latbench_pad zephyr_generated_headers)
  target_link_libraries(app PRIVATE latbench_pad)
  zephyr_code_relocate(FILES ${pad_src} LOCATION ${loc})
  set(probes lat_code_pad)

  if(CONFIG_LATBENCH_CODE_RAM_APP)
    zephyr_code_relocate(LIBRARY app LOCATION ${loc} NOKEEP)
    list(APPEND probes lat_meta_print)
  endif()
  if(CONFIG_LATBENCH_CODE_RAM_KERNEL)
    latbench_relocate_lib(kernel ${loc} "${kernel_exclude}")
    list(APPEND probes z_setup_new_thread)
  endif()
  if(CONFIG_LATBENCH_CODE_RAM_ARCH)
    latbench_relocate_lib(arch__arm__core__cortex_m ${loc} "${boot}")
    list(APPEND probes _isr_wrapper)
    if(mpu_lib AND CONFIG_ARM_MPU)
      latbench_relocate_lib(${mpu_lib} ${loc} "")
      list(APPEND probes z_arm_mpu_init)
    endif()
  endif()
  if(CONFIG_LATBENCH_CODE_RAM_DRIVERS)
    foreach(lib drivers__timer drivers__gpio drivers__interrupt_controller)
      if(TARGET ${lib})
        latbench_relocate_lib(${lib} ${loc} "")
      endif()
    endforeach()
    list(APPEND probes sys_clock_isr)
  endif()

  # Linker checks. Each probe is a function that each build keeps (the
  # garbage collection of the linker does not remove it). A probe that the
  # build does not have passes.
  set(ld "/* Generated by common/latbench.cmake */\n")
  string(APPEND ld "ASSERT(lat_code_pad == __${mem}_text_reloc_start, \"latbench: the code pad is not the first relocated function\")\n")
  foreach(sym ${probes})
    string(APPEND ld "ASSERT(!DEFINED(${sym}) || (${sym} >= __${mem}_text_reloc_start && ${sym} < __${mem}_text_reloc_end), \"latbench: ${sym} is not in the relocated code\")\n")
  endforeach()
  file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/latbench_code_ram.ld "${ld}")
  zephyr_linker_sources(SECTIONS ${CMAKE_CURRENT_BINARY_DIR}/latbench_code_ram.ld)

  # For lat_meta_print(): the symbols of the relocated text.
  target_compile_definitions(app PRIVATE LATBENCH_CODE_RAM_TEXT_START=__${mem}_text_reloc_start
    LATBENCH_CODE_RAM_TEXT_END=__${mem}_text_reloc_end)
endfunction()

if(CONFIG_LATBENCH_CODE_RAM)
  latbench_code_ram()
endif()
