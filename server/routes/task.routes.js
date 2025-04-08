import express from "express";

import {
    addTask,
    deleteTask,
    markTaskCompleted,
    getAllTasks
} from "../controllers/task.controllers.js";
import protectRoute from "../middleware/protectRoute.middleware.js";

const taskRouter = express.Router();

taskRouter.post("/add", protectRoute, addTask);                      // POST /api/tasks/add
taskRouter.delete("/:id", protectRoute, deleteTask);                 // DELETE /api/tasks/:id
taskRouter.patch("/complete/:id", protectRoute, markTaskCompleted);  // PATCH /api/tasks/complete/:id
taskRouter.get("/user", protectRoute, getAllTasks);          // GET /api/tasks/user/:userId

export default taskRouter;
