STACK_NAME ?= "sqs-import-error"

dev:
	pip install -r requirements-dev.txt

deploy:
	sam build --use-container && sam deploy
	
logs:
	sam logs --stack-name ${STACK_NAME} --tail
