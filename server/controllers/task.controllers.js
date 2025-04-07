import Task from "../models/task.models.js";
import User from "../models/user.models.js";

// Add new task
export const addTask = async (req, res) => {
    try {
        const task = new Task(req.body);
        const savedTask = await task.save();
        res.status(201).json(savedTask);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

// Delete a task
export const deleteTask = async (req, res) => {
    try {
        const task = await Task.findById(req.params.id);

        if (!task) {
            return res.status(404).json({ message: "Task not found" });
        }

        // Ownership check: make sure logged-in user owns the task
        if (task.user.toString() !== req.user._id.toString()) {
            return res.status(403).json({ message: "You are not authorized to delete this task" });
        }

        // Delete task
        await task.deleteOne();

        // Remove task from user's tasks list
        await User.findByIdAndUpdate(task.user, {
            $pull: { tasks: task._id }
        });

        res.status(200).json({ message: "Task deleted successfully" });
    } catch (error) {
        console.error("Error deleting task:", error.message);
        res.status(500).json({ error: "Internal server error" });
    }
};


// Mark task as completed
export const markTaskCompleted = async (req, res) => {
    try {
        const task = await Task.findById(req.params.id);

        if (!task) {
            return res.status(404).json({ message: "Task not found" });
        }

        // Ownership check
        if (task.user.toString() !== req.user._id.toString()) {
            return res.status(403).json({ message: "You are not authorized to update this task" });
        }

        // Toggle completion
        task.completed = !task.completed;
        task.completedAt = task.completed ? new Date() : null;

        const updatedTask = await task.save();

        res.status(200).json(updatedTask);
    } catch (error) {
        console.error("Error toggling task completion:", error.message);
        res.status(500).json({ error: "Internal server error" });
    }
};

// List all tasks for a user
export const getAllTasks = async (req, res) => {
    try {
        const tasks = await Task.find({ user: req.params.userId }).sort({ createdAt: -1 });
        res.status(200).json(tasks);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};
