# Introduction 
This repository represents a benchmark suite for cross-language energy measurement benchmarks using realistic workloads.

# Getting Started
TODO: Guide users through getting your code up and running on their own system. In this section you can talk about:
1.	Installation process
2.	Software dependencies
3.	Latest releases
4.	API references

A requirement to run this project is to install Docker.
Docker can be found and installed simply through a GUI here: [text](https://www.docker.com/products/docker-desktop/) 

# Build and Test
TODO: Describe and show how to build your code and run the tests. 
Step 1 | CD into main folder:
  CD into realistic-energy.

Step 2 | build Docker image:
  docker build -t realistic-energy -f docker/Dockerfile .

Step 3 | create Docker container, generate inputs and run benchmarks:
Default: generate sha256 datasets 1MiB->512MiB, build, run benchmarks
  docker run --rm -v ${PWD}:/realistic-energy realistic-energy

docker run --rm \
  --privileged \
  --cpuset-cpus=0 \
  -v /sys/class/powercap:/sys/class/powercap:ro \
  -v $(pwd):/realistic-energy \
  realistic-energy --iterations 100000

Generate altered datasets, then run
  docker run --rm -v "%cd%":/realistic-energy ^
  -e MIN_SIZE=X -e MAX_SIZE=Y realistic-energy

Force regenerate datasets
  docker run --rm -v "%cd%":/realistic-energy -e REGEN=1 realistic-energy

Only generate inputs (skip running benchmarks)
docker run --rm -v "%cd%":/realistic-energy realistic-energy \
  python3 scripts/generate_inputs.py --benchmarks sha256 --min-size 64 --max-size 1048576

Rebuilding when possibly containing bad cached config after changing settings can be done by running the following:
  docker run --rm -e REBUILD=1 -v ${PWD}:/realistic-energy realistic-energy

# Contribute
TODO: Explain how other users and developers can contribute to make your code better. 

If you want to learn more about creating good readme files then refer the following [guidelines](https://docs.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops). You can also seek inspiration from the below readme files:
- [ASP.NET Core](https://github.com/aspnet/Home)
- [Visual Studio Code](https://github.com/Microsoft/vscode)
- [Chakra Core](https://github.com/Microsoft/ChakraCore)