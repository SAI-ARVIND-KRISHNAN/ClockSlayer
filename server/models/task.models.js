import mongoose from "mongoose";

const taskSchema = new mongoose.Schema({
  // Ownership
  user: {
    type: mongoose.Schema.Types.ObjectId,
    ref: "User",
    required: true
  },

  // Task content
  title: {
    type: String,
    required: true,
    trim: true
  },
  description: {
    type: String,
    default: "",
    trim: true
  },
  type: {
    type: String,
    required: true, // e.g., "Work", "Personal", "Study"
    trim: true
  },
  priority: {
    type: String,
    enum: ["Low", "Medium", "High"],
    default: "Medium"
  },

  // Timing
  deadline: {
    type: Date,
    default: () => new Date(Date.now() + 24 * 60 * 60 * 1000) // 24 hours from now
  },
  reminderDate: {
    type: Date,
    default: function () {
      return new Date(this.deadline.getTime() - 5 * 60 * 60 * 1000); // 5 hours before deadline
    }
  },
  startedAt: {
    type: Date,
    default: null
  },
  completed: {
    type: Boolean,
    default: false
  },
  completedAt: {
    type: Date,
    default: null
  },

  // Metrics
  actualTimeSpent: {
    type: Number, // minutes
    default: null
  },
  distractionScore: {
    type: Number, // 0–100
    default: null
  },
  productivityScore: {
    type: Number, // 0–100
    default: null
  }

}, { timestamps: true });

const Task = mongoose.model("Task", taskSchema);
export default Task;
