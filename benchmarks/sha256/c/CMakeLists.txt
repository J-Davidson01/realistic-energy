cmake_minimum_required(VERSION 3.16)
project(sha256_bench C)

set(CMAKE_C_STANDARD 11)

find_package(OpenSSL REQUIRED)

add_executable(sha256 sha256.c)

target_link_libraries(sha256 PRIVATE OpenSSL::Crypto)