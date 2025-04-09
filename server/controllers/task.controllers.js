import axios from "axios";
import Task from "../models/task.models.js";
import User from "../models/user.models.js";

// Create a new task
export const addTask = async (req, res) => {
  try {
    const taskData = {
      ...req.body,
      priority: req.body.priority || "Medium",
      user: req.user._id
    };

    const task = new Task(taskData);
    const savedTask = await task.save();

    res.status(201).json(savedTask);
  } catch (error) {
    console.error("Error creating task:", error.message);
    res.status(500).json({ error: "Internal server error" });
  }
};

// Start a task (sets startedAt)
export const startTask = async (req, res) => {
  try {
    const task = await Task.findById(req.params.id);
    if (!task) return res.status(404).json({ message: "Task not found" });
    if (task.user.toString() !== req.user._id.toString()) {
      return res.status(403).json({ message: "Unauthorized" });
    }

    task.startedAt = new Date();
    await task.save();

    res.status(200).json(task);
  } catch (error) {
    console.error("Error starting task:", error.message);
    res.status(500).json({ error: "Internal server error" });
  }
};

// Delete a task
export const deleteTask = async (req, res) => {
  try {
    const task = await Task.findById(req.params.id);
    if (!task) return res.status(404).json({ message: "Task not found" });
    if (task.user.toString() !== req.user._id.toString()) {
      return res.status(403).json({ message: "Unauthorized" });
    }

    await task.deleteOne();

    await User.findByIdAndUpdate(task.user, {
      $pull: { tasks: task._id }
    });

    res.status(200).json({ message: "Task deleted successfully" });
  } catch (error) {
    console.error("Error deleting task:", error.message);
    res.status(500).json({ error: "Internal server error" });
  }
};

// Complete a task (toggle)
export const markTaskCompleted = async (req, res) => {
  try {
    const task = await Task.findById(req.params.id);
    if (!task) return res.status(404).json({ message: "Task not found" });

    if (task.user.toString() !== req.user._id.toString()) {
      return res.status(403).json({ message: "Unauthorized" });
    }

    if (!task.startedAt && !task.completed) {
      return res.status(400).json({ message: "Task must be started before it can be marked as completed" });
    }

    const now = new Date();
    const startTime = task.startedAt || task.createdAt;
    const durationMinutes = Math.round((now - new Date(startTime)) / (1000 * 60));

    // Toggle completion
    task.completed = !task.completed;
    task.completedAt = task.completed ? now : null;
    task.actualTimeSpent = task.completed ? durationMinutes : null;

    if (task.completed) {
      const user = await User.findById(task.user);

      const prodInput = req.body?.productivityScore;
      const distractInput = req.body?.distractionScore;

      const hasProd = typeof prodInput === "number" && prodInput >= 1 && prodInput <= 10;
      const hasDistract = typeof distractInput === "number" && distractInput >= 1 && distractInput <= 10;

      if (hasProd) task.productivityScore = prodInput * 10;
      if (hasDistract) task.distractionScore = distractInput * 10;

      // Fallback scoring
      if (!hasProd || !hasDistract) {
        const payload = {
          timeOfDay: startTime.getHours() < 12 ? 0 : startTime.getHours() < 18 ? 1 : 2,
          dayOfWeek: startTime.getDay(),
          activity_type: ["Work", "Personal", "Study", "Errands"].indexOf(task.type),
          completedTasks: 1,
          distractions: Math.floor(Math.random() * 5), // Replace with actual signal
          idleTime: 0, // Replace with actual idle signal
          energy: user?.currentEnergyLevel || 5,
          mood: 0 // Replace with mood mapping if needed
        };

        try {
          const { data } = await axios.post("http://localhost:8001/score", payload);
          if (!hasProd) task.productivityScore = data.productivity_score ?? null;
          if (!hasDistract) task.distractionScore = data.distraction_score ?? null;
        } catch (err) {
          console.warn("⚠️ Scoring service fallback failed:", err.message);
        }
      }

      // 🔄 Recompute baseline productivity and distraction
      const completedTasks = await Task.find({
        user: task.user,
        completed: true,
        productivityScore: { $ne: null },
        distractionScore: { $ne: null }
      });

      if (completedTasks.length > 0) {
        const totalProd = completedTasks.reduce((sum, t) => sum + t.productivityScore, 0);
        const totalDist = completedTasks.reduce((sum, t) => sum + t.distractionScore, 0);

        user.baselineProductivityScore = Math.round(totalProd / completedTasks.length);
        user.baselineDistractionScore = Math.round(totalDist / completedTasks.length);
        await user.save();
      }
    }

    const updatedTask = await task.save();
    return res.status(200).json(updatedTask);

  } catch (err) {
    console.error("❌ Error in markTaskCompleted:", err.message);
    return res.status(500).json({ error: "Internal server error" });
  }
};



// Get all active (not started, not completed) tasks
export const getAllTasks = async (req, res) => {
  try {
    const tasks = await Task.find({
      user: req.user._id,
      completed: false,
      startedAt: null
    }).sort({ createdAt: -1 });

    const user = await User.findById(req.user._id);

    const enrichedTasks = await Promise.all(
      tasks.map(async (task) => {
        try {
          // === Get ETC ===
          const now = new Date();
          const startTime = now;
          const deadline = new Date(task.deadline);
          const deadlineGap = (deadline - startTime) / (1000 * 60 * 60);
          const dayOfWeek = startTime.getUTCDay();
          const hourOfDay = startTime.getUTCHours();
          const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
          const timeOfDay = hourOfDay < 12 ? "Morning" : hourOfDay < 18 ? "Afternoon" : "Evening";
          const hasDescription = !!(task.description && task.description.trim().length > 0);
          const titleLength = task.title.trim().split(" ").length;
          const timeToDeadline = (deadline - now) / (1000 * 60 * 60);
          const urgency = timeToDeadline < 12 ? "Urgent" : timeToDeadline < 24 ? "Soon" : "Low";
          const taskLength = titleLength < 3 ? "Short" : titleLength < 6 ? "Medium" : "Long";

          const etcPayload = {
            user_id: task.user.toString(),
            type: task.type,
            priority: task.priority,
            deadline_gap: deadlineGap,
            dayOfWeek,
            hourOfDay,
            isWeekend,
            timeOfDay,
            hasDescription,
            titleLength,
            urgency,
            taskLength,
            productivityScore: user?.baselineProductivityScore || 50,
            distractionScore: user?.baselineDistractionScore || 50
          };

          const etcResponse = await axios.post("http://localhost:8000/predict", etcPayload);

          // === Get predicted productivity & distraction scores ===
          const scoreResponse = await axios.post("http://localhost:7060/score", {
            user_id: task.user.toString(),
            task_id: task._id.toString()
          });

          return {
            ...task.toObject(),
            etc: etcResponse.data["Formatted ETC"],
            etc_minutes: etcResponse.data["Estimated Time of Completion (in minutes)"],
            predictedProductivityScore: scoreResponse.data.productivity_score || null,
            predictedDistractionScore: scoreResponse.data.distraction_score || null
          };
        } catch (err) {
          console.error(`❌ Error enriching task "${task.title}":`, err.message);
          return {
            ...task.toObject(),
            etc: "ETC unavailable",
            etc_minutes: null,
            predictedProductivityScore: null,
            predictedDistractionScore: null
          };
        }
      })
    );

    res.status(200).json(enrichedTasks);
  } catch (error) {
    console.error("❌ Error fetching tasks:", error.message);
    res.status(500).json({ error: "Internal server error" });
  }
};
