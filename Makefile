.PHONY: test run-uk run-us run-both help

test:
	python3 -m pytest tests -v

run-uk:
	python3 tinyverify.py --name "Tesco" --jurisdiction UK

run-us:
	python3 tinyverify.py --name "Apple" --jurisdiction US

run-both:
	python3 tinyverify.py --name "Tesco" --jurisdiction BOTH --monitor

help:
	python3 tinyverify.py --help
