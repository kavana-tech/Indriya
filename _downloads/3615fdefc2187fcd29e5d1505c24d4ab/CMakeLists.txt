cmake_minimum_required(VERSION 3.16)
project(MudraSDK LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)

# Resolve mudra_sdk/libs/<platform>/<arch>/ layout used by library_loader.py
if(WIN32)
  set(MUDRA_PLATFORM_DIR "windows")
  if(CMAKE_SIZEOF_VOID_P EQUAL 8)
    set(MUDRA_ARCH_DIR "x64")
  else()
    set(MUDRA_ARCH_DIR "x86")
  endif()
  set(MUDRA_LIB_FILENAME "MudraSDK.dll")
elseif(APPLE)
  set(MUDRA_PLATFORM_DIR "darwin")
  if(CMAKE_OSX_ARCHITECTURES STREQUAL "x86_64")
    set(MUDRA_ARCH_DIR "x86_64")
  elseif(CMAKE_OSX_ARCHITECTURES STREQUAL "arm64")
    set(MUDRA_ARCH_DIR "arm64")
  elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "arm64|aarch64")
    set(MUDRA_ARCH_DIR "arm64")
  else()
    set(MUDRA_ARCH_DIR "x86_64")
  endif()
  set(MUDRA_LIB_FILENAME "MudraSDK.dylib")
elseif(ANDROID)
  set(MUDRA_PLATFORM_DIR "android")
  if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
    set(MUDRA_ARCH_DIR "aarch64")
  elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "arm")
    set(MUDRA_ARCH_DIR "arm")
  else()
    set(MUDRA_ARCH_DIR "x86_64")
  endif()
  set(MUDRA_LIB_FILENAME "MudraSDK.so")
else()
  set(MUDRA_PLATFORM_DIR "linux")
  if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
    set(MUDRA_ARCH_DIR "aarch64")
  else()
    set(MUDRA_ARCH_DIR "x86_64")
  endif()
  set(MUDRA_LIB_FILENAME "MudraSDK.so")
endif()

set(MUDRA_LIBS_OUT_DIR
  "${CMAKE_CURRENT_SOURCE_DIR}/../libs/${MUDRA_PLATFORM_DIR}/${MUDRA_ARCH_DIR}"
  CACHE PATH "Output directory for MudraSDK native library"
)

add_library(MudraSDK SHARED
  computation_wrapper.cpp
  Computation/ProCdcCommands.cpp
  Computation/UltimateCdcCommands.cpp
  Computation/ComputationManager.cpp
  Computation/DataRecorder.cpp
  Computation/ProFirmwareCommands.cpp
  Computation/UltimateFirmwareCommands.cpp
  Computation/json11.cpp
  Computation/Logging.cpp
  Computation/Parser.cpp
  Computation/PrioritySizedQueues.cpp
  Computation/SignalAnalyzer.cpp
  Computation/SizedQueues.cpp
  Computation/Timer.cpp
)

target_include_directories(MudraSDK
  PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}"
    "${CMAKE_CURRENT_SOURCE_DIR}/Computation"
)

target_compile_definitions(MudraSDK
  PRIVATE
    MUDRA_API_BUILD
    MUDRAWINDOWSDESKTOP_EXPORTS
    $<$<PLATFORM_ID:Windows>:_WINDOWS>
    $<$<PLATFORM_ID:Windows>:NOMINMAX>
    $<$<PLATFORM_ID:Windows>:WIN32_LEAN_AND_MEAN>
)

# library_loader expects MudraSDK.<ext>, not libMudraSDK.<ext>
set_target_properties(MudraSDK PROPERTIES
  OUTPUT_NAME "MudraSDK"
  PREFIX ""
  RUNTIME_OUTPUT_DIRECTORY "${MUDRA_LIBS_OUT_DIR}"
  LIBRARY_OUTPUT_DIRECTORY "${MUDRA_LIBS_OUT_DIR}"
  ARCHIVE_OUTPUT_DIRECTORY "${MUDRA_LIBS_OUT_DIR}"
  RUNTIME_OUTPUT_DIRECTORY_DEBUG "${MUDRA_LIBS_OUT_DIR}"
  RUNTIME_OUTPUT_DIRECTORY_RELEASE "${MUDRA_LIBS_OUT_DIR}"
  LIBRARY_OUTPUT_DIRECTORY_DEBUG "${MUDRA_LIBS_OUT_DIR}"
  LIBRARY_OUTPUT_DIRECTORY_RELEASE "${MUDRA_LIBS_OUT_DIR}"
  ARCHIVE_OUTPUT_DIRECTORY_DEBUG "${MUDRA_LIBS_OUT_DIR}"
  ARCHIVE_OUTPUT_DIRECTORY_RELEASE "${MUDRA_LIBS_OUT_DIR}"
)

if(MSVC)
  target_compile_options(MudraSDK PRIVATE /W3 /EHsc)
else()
  target_compile_options(MudraSDK PRIVATE -Wall -Wextra)
endif()

message(STATUS "MudraSDK will be written to: ${MUDRA_LIBS_OUT_DIR}/${MUDRA_LIB_FILENAME}")
