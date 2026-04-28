cmake_minimum_required(VERSION 3.16)
project(json_parse C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_executable(json_parse_c
    json_parse_main.c
    ../../workloads/c/json_parse_workload.c
)

target_include_directories(json_parse_c PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

find_package(PkgConfig REQUIRED)
pkg_check_modules(CJSON REQUIRED libcjson)

target_include_directories(json_parse_c PRIVATE ${CJSON_INCLUDE_DIRS})
target_link_directories(json_parse_c PRIVATE ${CJSON_LIBRARY_DIRS})
target_link_libraries(json_parse_c PRIVATE ${CJSON_LIBRARIES})