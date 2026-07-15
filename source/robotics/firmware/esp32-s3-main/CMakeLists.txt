# HK-07 ESP32-S3 Main Controller — CMakeLists.txt
cmake_minimum_required(VERSION 3.16)

set(EXTRA_COMPONENT_DIRS "")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)

project(hk07_s3_main)
