#!/usr/bin/env node
const { DynamoDBClient, PutItemCommand } = require('@aws-sdk/client-dynamodb');

const TABLE = process.env.ALLOWED_USERS_TABLE || process.argv[2];
const email = process.argv[3] || process.argv[2];

if (!TABLE || !email) {
    console.error('Usage: ALLOWED_USERS_TABLE=<table> node create_allowed_user.js <table> <email>\nOr: ALLOWED_USERS_TABLE=<table> node create_allowed_user.js <email>');
    process.exit(2);
}

const dynamo = new DynamoDBClient({});

(async () => {
    try {
        const cmd = new PutItemCommand({
            TableName: TABLE,
            Item: {
                email: { S: email.toLowerCase() }
            }
        });
        await dynamo.send(cmd);
        console.log('Added allowed user', email.toLowerCase(), 'to', TABLE);
    } catch (err) {
        console.error('Error adding allowed user', err);
        process.exit(1);
    }
})();
