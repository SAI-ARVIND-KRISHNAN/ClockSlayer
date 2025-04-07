import mongoose from "mongoose";

const taskSchema = new mongoose.Schema({
    user: {
        type: mongoose.Schema.Types.ObjectId,
        ref: "User",
        required: true
    },
    title: {
        type: String,
        required: true
    },
    description: {
        type: String,
        default: ""
    },
    type: {
        type: String, // e.g., "Work", "Personal", "Study"
        required: true
    },
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
    completed: {
        type: Boolean,
        default: false
    },
    completedAt: {
        type: Date,
        default: null
    }
}, { timestamps: true });

const Task = mongoose.model("Task", taskSchema);

export default Task;
