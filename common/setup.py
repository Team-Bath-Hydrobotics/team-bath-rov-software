from setuptools import find_packages, setup

setup(
    name="bathrov-common",
    version="1.0.1",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "common.mqtt": ["schemas/*.json", "topics.yaml"],
    },
    install_requires=[],
)
