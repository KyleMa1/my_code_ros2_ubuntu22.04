import os
from glob import glob

from setuptools import setup

package_name = "recommend_py"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="dev",
    maintainer_email="dev@example.com",
    description="Python application layer: patrol planning and AI-like decisions",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "patrol_planner = recommend_py.patrol_planner:main",
        ],
    },
)
