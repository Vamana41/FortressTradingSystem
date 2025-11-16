
from setuptools import setup
from setuptools_rust import Binding, RustExtension

setup(
    name="fortress_rust_extensions",
    version="1.0.0",
    rust_extensions=[
        RustExtension(
            "fortress_rust.fast_math",
            path="src/fast_math/Cargo.toml",
            binding=Binding.PyO3
        ),
        RustExtension(
            "fortress_rust.data_structures",
            path="src/data_structures/Cargo.toml",
            binding=Binding.PyO3
        ),
        RustExtension(
            "fortress_rust.market_data",
            path="src/market_data/Cargo.toml",
            binding=Binding.PyO3
        )
    ],
    packages=["fortress_rust"],
    zip_safe=False,
)
