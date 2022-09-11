build: requirements.txt
	echo $@
	mkdir build
	cp *.py $@/.
	cp requirements.txt $@/.
	cd $@ && docker build -t newsgen -f ../Dockerfile .	

clean:
	rm -rf build

enter:
	docker run -it --entrypoint /bin/bash --rm -v `pwd`:/code newsgen

requirements.txt: requirements.in
	pip-compile
