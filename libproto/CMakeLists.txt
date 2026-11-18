cmake_minimum_required(VERSION 3.16)
project(libproto C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
add_compile_options(-Wall -Wextra -Wpedantic)

set(PROTO_SRC
  src/siphash.c
  src/crypto_backend.c
  src/kdf.c
  src/hop.c
  src/hop_gap.c
  src/packet.c
  src/resync.c
)

add_library(proto SHARED ${PROTO_SRC})
target_include_directories(proto PUBLIC include)

add_library(proto_static STATIC ${PROTO_SRC})
target_include_directories(proto_static PUBLIC include)

enable_testing()
add_executable(test_proto tests/test_main.c)
target_link_libraries(test_proto proto_static)
add_test(NAME test_proto COMMAND test_proto)
