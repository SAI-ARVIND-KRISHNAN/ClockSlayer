import http from 'http';
import dotenv from "dotenv";
import cluster from 'cluster';
import os from 'os';

import app from './App.js';
import connectMongoDB from './db/connectMongoDB.js';

dotenv.config();
console.log("Mongo URI:", process.env.MONGO_URI);
console.log("Mongo URI:", process.env.PORT);


const PORT = process.env.PORT || 8000;

const server = http.createServer(app);
/*
if (cluster.isPrimary) {
    console.log("Master process has started...")
    const NUM_WORKER = os.cpus().length;

    for (let i = 0; i < NUM_WORKER; i++) {
        cluster.fork();
    }
} else {
    server.listen(PORT, () => {
        console.log(`Server running at ${PORT}...`);
        connectMongoDB();
    });
}
    */
server.listen(PORT, () => {
    console.log(`Server running at ${PORT}...`);
    connectMongoDB();
});