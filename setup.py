from setuptools import setup, find_packages

setup(
    name="xray-python",
    version="0.1.0",
    description="Python API для управления пользователями Xray",
    author="Kafka",
    author_email="kafka_mas@disroot.org",
    packages=find_packages(),
    install_requires=[
        "dnspython>=2.8.0",
        "email-validator>=2.3.0",
        "grpcio>=1.78.0",
        "grpcio-tools>=1.78.0",
        "idna>=3.11",
        "protobuf>=6.33.5",
        "setuptools>=82.0.0",
        "typing_extensions>=4.15.0",
    ],
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)