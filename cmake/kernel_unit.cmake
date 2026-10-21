# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

# Shared setup for the kernel unit test applications. Include this file
# after find_package(Zephyr COMPONENTS unittest):
#
#   include(${ZEPHYR_SAFETY_MODULE_DIR}/cmake/kernel_unit.cmake)
#
# A kernel unit test builds one kernel source file (for example
# kernel/sem.c) into the test binary. The test source includes the .c file,
# so that the tests can also call its static functions. The kernel itself
# does not start.
#
# The shadow headers in tests/kernel/unit/common/include come before every
# Zephyr include directory. They replace the kernel-internal headers and
# the arch layer with FFF fakes. kernel/include is not on the include path:
# a kernel source that includes a new internal header does not compile
# until the header has a shadow.

if(NOT DEFINED ZEPHYR_SAFETY_MODULE_DIR)
  message(FATAL_ERROR "kernel_unit: the safety module is not known to the build "
                      "(ZEPHYR_SAFETY_MODULE_DIR is not set)")
endif()

set(KERNEL_UNIT_COMMON_DIR ${ZEPHYR_SAFETY_MODULE_DIR}/tests/kernel/unit/common)

# unittest.cmake sets -m32 (or -m64 with M64_MODE) for every host except
# macOS. GCC on an aarch64 host knows neither option, so the build uses the
# native ABI there.
if(CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "^(aarch64|arm64)$")
  set(CMAKE_C_FLAGS "")
  set(CMAKE_CXX_FLAGS "")
endif()

target_include_directories(testbinary BEFORE PRIVATE ${KERNEL_UNIT_COMMON_DIR}/include)

target_sources(testbinary PRIVATE ${KERNEL_UNIT_COMMON_DIR}/fakes/fff_globals.c)

# SHELL: keeps "-T <script>" together; CMake removes a repeated plain -T
# (unittest.cmake adds one for ztest_unittest.ld).
target_link_options(testbinary PRIVATE "SHELL:-T ${KERNEL_UNIT_COMMON_DIR}/kernel_unit.ld")

# Drift guard of the real copies in the shadow headers. A shadow header can
# keep a pure function of a kernel-internal header real, as a copy of its
# text between the markers KERNEL_UNIT_REAL_COPY_BEGIN and
# KERNEL_UNIT_REAL_COPY_END. common/check_real_copies.py examines that each
# copy is still the same as the text of the real header. If not, the
# configuration stops. A change of a shadow header or of a real header runs
# the check again.
file(GLOB KERNEL_UNIT_SHADOW_HEADERS ${KERNEL_UNIT_COMMON_DIR}/include/*.h)
file(GLOB KERNEL_UNIT_REAL_HEADERS ${ZEPHYR_BASE}/kernel/include/*.h)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  ${KERNEL_UNIT_SHADOW_HEADERS} ${KERNEL_UNIT_REAL_HEADERS}
  ${KERNEL_UNIT_COMMON_DIR}/check_real_copies.py)
execute_process(
  COMMAND ${PYTHON_EXECUTABLE} ${KERNEL_UNIT_COMMON_DIR}/check_real_copies.py
          ${ZEPHYR_BASE} ${KERNEL_UNIT_SHADOW_HEADERS}
  RESULT_VARIABLE kernel_unit_check_result
  OUTPUT_VARIABLE kernel_unit_check_output
  ERROR_VARIABLE kernel_unit_check_output
)
if(NOT kernel_unit_check_result EQUAL 0)
  message(FATAL_ERROR "kernel_unit: a real copy in a shadow header is not up to date:\n"
                      "${kernel_unit_check_output}")
endif()

# Guard against an undefined macro in #if. The preprocessor gives an
# undefined macro the value 0 without a diagnostic. Thus a removed macro
# (for example Z_MUTEX_PI_ENABLED) removes the tests in its #if blocks, and
# the run passes. With -Werror=undef, the build stops.
target_compile_options(testbinary PRIVATE -Wundef -Werror=undef)

# ztest.c (upstream) has "#if CONFIG_ZTEST_SHUFFLE", and the option is a
# bool. ztest.c is the only source with this warning, so only ztest.c is
# compiled without -Wundef. The source option comes after the target options
# on the command line.
set_source_files_properties(${ZEPHYR_BASE}/subsys/testsuite/ztest/src/ztest.c
  PROPERTIES COMPILE_OPTIONS -Wno-undef)

# zephyr/kernel.h has "#if (K_HEAP_MEM_POOL_SIZE > 0)". In a real build,
# kernel/CMakeLists.txt defines K_HEAP_MEM_POOL_SIZE on the command line.
# The unittest build does not read this file. The harness gives the same
# value as the real build with CONFIG_KERNEL_MEM_POOL, but without the
# requests of the CONFIG_HEAP_MEM_POOL_ADD_SIZE_* options. Without
# CONFIG_KERNEL_MEM_POOL, the value is 0 (the real build has no
# definition, and #if gives it the value 0).
if(CONFIG_KERNEL_MEM_POOL)
  target_compile_definitions(testbinary PRIVATE K_HEAP_MEM_POOL_SIZE=${CONFIG_HEAP_MEM_POOL_SIZE})
else()
  target_compile_definitions(testbinary PRIVATE K_HEAP_MEM_POOL_SIZE=0)
endif()

# Test inventory check. The binary compares its tests and their state (run
# or skip) with the expected set of the twister scenario,
# <application>/inventory/<scenario>.txt. Thus a change that removes a test
# without a diagnostic makes the run fail. See common/test_inventory.py and
# common/src/test_inventory.c.
#
# Twister gives the scenario name in TC_NAME. For a build without twister,
# give it with -DKERNEL_UNIT_SCENARIO=<scenario>. Without a scenario name,
# the check is off.
if(NOT DEFINED KERNEL_UNIT_SCENARIO AND DEFINED TC_NAME)
  # With --detailed-test-id, TC_NAME starts with the path of the application.
  string(REGEX REPLACE "^.*/" "" KERNEL_UNIT_SCENARIO "${TC_NAME}")
endif()
if(NOT "${KERNEL_UNIT_SCENARIO}" STREQUAL "")
  set(kernel_unit_inventory_dir ${CMAKE_CURRENT_SOURCE_DIR}/inventory)
  set(kernel_unit_inventory_file ${kernel_unit_inventory_dir}/${KERNEL_UNIT_SCENARIO}.txt)
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    ${KERNEL_UNIT_COMMON_DIR}/test_inventory.py)
  if(EXISTS ${kernel_unit_inventory_dir})
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${kernel_unit_inventory_dir})
  else()
    message(WARNING "kernel_unit: the application has no expected test inventory "
                    "(${kernel_unit_inventory_dir}). The inventory check is off. "
                    "To make the expected sets, see \"Test inventory\" in README.rst.")
  endif()
  if(EXISTS ${kernel_unit_inventory_file})
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${kernel_unit_inventory_file})
  endif()
  execute_process(
    COMMAND ${PYTHON_EXECUTABLE} ${KERNEL_UNIT_COMMON_DIR}/test_inventory.py gen
            --app-dir ${CMAKE_CURRENT_SOURCE_DIR}
            --scenario ${KERNEL_UNIT_SCENARIO}
            --build-dir ${APPLICATION_BINARY_DIR}
    RESULT_VARIABLE kernel_unit_inventory_result
    OUTPUT_VARIABLE kernel_unit_inventory_output
    ERROR_VARIABLE kernel_unit_inventory_output
  )
  if(NOT kernel_unit_inventory_result EQUAL 0)
    message(FATAL_ERROR "kernel_unit: the expected test inventory is not correct:\n"
                        "${kernel_unit_inventory_output}")
  endif()
  target_sources(testbinary PRIVATE ${KERNEL_UNIT_COMMON_DIR}/src/test_inventory.c)
  set_source_files_properties(${KERNEL_UNIT_COMMON_DIR}/src/test_inventory.c
    PROPERTIES INCLUDE_DIRECTORIES ${APPLICATION_BINARY_DIR}/kernel_unit)
else()
  message(STATUS "kernel_unit: no scenario name (TC_NAME or KERNEL_UNIT_SCENARIO), "
                 "the test inventory check is off")
endif()

# Native gcov backend of the ztest per-test coverage rule (see
# common/Kconfig and common/src/gcov_native.c).
if(CONFIG_ZTEST_COVERAGE_PER_TEST)
  target_sources(testbinary PRIVATE ${KERNEL_UNIT_COMMON_DIR}/src/gcov_native.c)
endif()

# With CONFIG_COVERAGE, the target "coverage" runs the test binary and
# writes a gcovr report of the kernel sources (ZEPHYR_BASE/kernel) to
# <build>/coverage/index.html. The report leaves out ztest, the fakes and
# the test sources. gcovr deletes the .gcda files after the report, so each
# report shows one run.
if(CONFIG_COVERAGE)
  find_program(KERNEL_UNIT_GCOVR gcovr)
  if(KERNEL_UNIT_GCOVR)
    add_custom_target(coverage
      COMMAND $<TARGET_FILE:testbinary>
      COMMAND ${CMAKE_COMMAND} -E make_directory ${APPLICATION_BINARY_DIR}/coverage
      COMMAND ${KERNEL_UNIT_GCOVR}
              --root ${ZEPHYR_BASE}/kernel
              --delete
              --txt
              --html-details ${APPLICATION_BINARY_DIR}/coverage/index.html
              ${APPLICATION_BINARY_DIR}
      DEPENDS testbinary
      WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
      USES_TERMINAL
    )
  else()
    message(WARNING "kernel_unit: gcovr not found, no target 'coverage'")
  endif()
endif()

# kernel_unit_fakes(<group>...)
#
# Links the FFF fake definitions of each group (common/fakes/<group>.c).
# A group defines the fakes of one or more shadow headers. Do not link a
# group that fakes a function the unit under test defines. For each group,
# the sources get the definition KERNEL_UNIT_FAKE_GROUP_<group>, so that a
# shared header can refer to the fakes of a linked group only.
function(kernel_unit_fakes)
  foreach(group ${ARGN})
    set(src ${KERNEL_UNIT_COMMON_DIR}/fakes/${group}.c)
    if(NOT EXISTS ${src})
      message(FATAL_ERROR "kernel_unit_fakes: no fake group '${group}' (${src})")
    endif()
    target_sources(testbinary PRIVATE ${src})
    target_compile_definitions(testbinary PRIVATE KERNEL_UNIT_FAKE_GROUP_${group}=1)
  endforeach()
endfunction()

# kernel_unit_fakes_ifdef(<feature> <group>...)
#
# Like kernel_unit_fakes(), but only if <feature> is true, for example a
# Kconfig option:
#
#   kernel_unit_fakes_ifdef(CONFIG_OBJ_CORE obj_core)
function(kernel_unit_fakes_ifdef feature)
  if(${${feature}})
    kernel_unit_fakes(${ARGN})
  endif()
endfunction()
