#include "cpp_pkg/cpp_pkg.h"

#include <cassert>
#include <iostream>

int main() {
    std::string result = cpp_pkg::greet("World");
    assert(result == "Hello from C++, World!");
    std::cout << "All tests passed.\n";
    return 0;
}
