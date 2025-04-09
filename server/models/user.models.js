import mongoose from "mongoose";

const userSchema = new mongoose.Schema({
  // Basic user authentication and identity
  username: {
    type: String,
    required: true,
    unique: true,
    trim: true
  },
  fullName: {
    type: String,
    required: true,
    trim: true
  },
  password: {
    type: String,
    required: true,
    minlength: 6
  },
  email: {
    type: String,
    required: true,
    unique: true,
    trim: true
  },

  // Observation phase tracking
  observationStart: {
    type: Date,
    default: Date.now
  },
  aiFeaturesUnlocked: {
    type: Boolean,
    default: false
  },

  // Baseline scores (periodically recalculated)
  baselineProductivityScore: {
    type: Number,
    default: 50
  },
  baselineDistractionScore: {
    type: Number,
    default: 50
  },

  // Real-time session state
  currentFocusLevel: {
    type: Number,
    default: 50 // Range: 0–100
  },
  currentEnergyLevel: {
    type: Number,
    default: 5   // Range: 1–10
  },
  currentMood: {
    type: String,
    enum: ["Neutral", "Happy", "Stressed", "Tired", "Motivated"],
    default: "Neutral"
  },

  // Energy log history
  energyLog: [
    {
      level: {
        type: Number,
        required: true
      },
      timestamp: {
        type: Date,
        default: Date.now
      },
      source: {
        type: String,
        default: "self_report"
      }
    }
  ],

  // Recently completed tasks for trend tracking
  recentCompletedTasks: [
    {
      taskId: {
        type: mongoose.Schema.Types.ObjectId,
        ref: "Task"
      },
      completedAt: {
        type: Date
      }
    }
  ],

  // LLM-based coaching memory (chat history)
  coachingHistory: [
    {
      message: {
        type: String,
        required: true
      },
      timestamp: {
        type: Date,
        default: Date.now
      }
    }
  ],

  // Task associations
  tasks: [
    {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Task",
      default: []
    }
  ]
}, { timestamps: true });

const User = mongoose.model("User", userSchema);
export default User;
