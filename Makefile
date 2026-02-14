IMAGE_NAME=mfn_cleaning_bot
TAG=latest

build:
	docker build . -t $(IMAGE_NAME):$(TAG)

compose:
	docker-compose up -d

deploy: build compose