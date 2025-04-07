import mongoose from "mongoose";

const userSchema = new mongoose.Schema({
    username: {
        type: String,
        required: true,
        unique: true,
    },
    fullName: {
        type: String,
        required: true
    },
    password: {
        type: String,
        required: true,
        minLength: 6
    },
    email: {
        type: String,
        required: true,
        unique: true
    },
    productivityScore: {
        type: Number,
        default: 0
    },
    productivityBlocks: [
        {
            type: mongoose.Schema.Types.ObjectId,
            ref: "ProductivityBlock",
            default: []
        }
    ]
}, { timestamps: true });

const User = mongoose.model("User", userSchema);

export default User;
