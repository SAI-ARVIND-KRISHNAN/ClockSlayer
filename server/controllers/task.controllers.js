import axios from "axios";
import Task from "../models/task.models.js";
import User from "../models/user.models.js";

// Add new task
export const addTask = async (req, res) => {
    try {
        // Default priority to 'Medium' if not provided
        const taskData = {
            ...req.body,
            priority: req.body.priority || "Medium",
            user: req.user._id
        };

        const task = new Task(taskData);
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
        const actualTimeSpent = Math.round((Date.now() - new Date(task.createdAt)) / (1000 * 60));

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
        const tasks = await Task.find({ user: req.user._id }).sort({ createdAt: -1 });
        const user = await User.findById(req.user._id); // For productivityScore

        const enrichedTasks = await Promise.all(
            tasks.map(async (task) => {
                if (task.completed) {
                    return {
                        ...task.toObject(),
                        etc: "Completed",
                        etc_minutes: null
                    };
                }

                try {
                    const created = new Date(task.createdAt);
                    const deadline = new Date(task.deadline);
                    const now = new Date();

                    const deadlineGap = (deadline - created) / (1000 * 60 * 60); // in hours
                    const dayOfWeek = created.getUTCDay(); // 0 = Sunday
                    const hourOfDay = created.getUTCHours();
                    const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
                    const timeOfDay = hourOfDay < 12 ? "Morning" : hourOfDay < 18 ? "Afternoon" : "Evening";
                    const hasDescription = task.description && task.description.trim().length > 0;
                    const titleLength = task.title.trim().split(" ").length;
                    const timeToDeadline = (deadline - now) / (1000 * 60 * 60); // in hours
                    const urgency = timeToDeadline < 12 ? "Urgent" : timeToDeadline < 24 ? "Soon" : "Low";
                    const taskLength = titleLength < 3 ? "Short" : titleLength < 6 ? "Medium" : "Long";

                    const requestPayload = {
                        user_id: task.user.toString(),
                        type: task.type,
                        priority: task.priority || "Medium",
                        deadline_gap: deadlineGap,
                        dayOfWeek,
                        hourOfDay,
                        isWeekend,
                        timeOfDay,
                        hasDescription,
                        titleLength,
                        urgency,
                        taskLength,
                        productivityScore: user.productivityScore || 50
                    };

                    const response = await axios.post("http://localhost:8000/predict", requestPayload);

                    return {
                        ...task.toObject(),
                        etc: response.data["Formatted ETC"],
                        etc_minutes: response.data["Estimated Time of Completion (in minutes)"]
                    };

                } catch (err) {
                    console.error(`❌ ETC fetch failed for task "${task.title}":`, err.message);
                    return {
                        ...task.toObject(),
                        etc: "ETC unavailable",
                        etc_minutes: null
                    };
                }
            })
        );

        res.status(200).json(enrichedTasks);
    } catch (error) {
        console.error("Error fetching tasks:", error.message);
        res.status(500).json({ error: "Internal server error" });
    }
};