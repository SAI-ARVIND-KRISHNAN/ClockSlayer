import express from "express";
import { createLog } from "../controllers/log.controllers.js";
import protectRoute from "../middleware/protectRoute.middleware.js";

const logRouter = express.Router();

logRouter.post("/", protectRoute , createLog); // POST /api/logs

export default logRouter;