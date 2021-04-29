PYTHON_VERSION = 3.9

all:	help

help:
	@echo "> help: Show this"
	@echo "> lint: Run linters"
	@echo "> test: Run tests"
	@echo "> docker: Run tests in Docker (default PYTHON_VERSION=$(PYTHON_VERSION))"

lint:
	pylint infer_parser
	flake8 --max-complexity=7 infer_parser
	mypy --strict infer_parser

test:
	pytest --cov=infer_parser --cov-report=term-missing

dist:
	python setup.py sdist bdist_wheel

docker:
	docker build -t test-infer-parser --build-arg PYTHON_IMAGE=python:$(PYTHON_VERSION)-alpine .
	docker run test-infer-parser

.PHONY:	all dist docker help lint test
