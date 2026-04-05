from setuptools import setup

package_name = "py_pkg"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="dev",
    maintainer_email="dev@example.com",
    description="Python ROS2 benchmark package",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "topic_pub = py_pkg.topic_publisher:main",
            "topic_sub = py_pkg.topic_subscriber:main",
            "service_server = py_pkg.service_server:main",
            "service_client = py_pkg.service_client:main",
            "action_server = py_pkg.action_server:main",
            "action_client = py_pkg.action_client:main",
            "param_node = py_pkg.param_node:main",
            "benchmark_node = py_pkg.benchmark_node:main",
        ],
    },
)
