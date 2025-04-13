import express from "express";
import {
  addTask,
  deleteTask,
  startTask,
  markTaskCompleted,
  getAllTasks
} from "../controllers/task.controllers.js";
import protectRoute from "../middleware/protectRoute.middleware.js";

const taskRouter = express.Router();

// POST /api/tasks/add - Create a new task
taskRouter.post("/add", protectRoute, addTask);

// GET /api/tasks/user - Get all tasks that are not started or completed
taskRouter.get("/user", protectRoute, getAllTasks);

// PATCH /api/tasks/start/:id - Start a task (set startedAt)
taskRouter.patch("/start/:id", protectRoute, startTask);

// PATCH /api/tasks/complete/:id - Toggle task completion
taskRouter.patch("/complete/:id", protectRoute, markTaskCompleted);

// DELETE /api/tasks/:id - Delete a task by ID
taskRouter.delete("/:id", protectRoute, deleteTask);

export default taskRouter;
