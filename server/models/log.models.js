import mongoose from "mongoose";

const LogSchema = new mongoose.Schema({
  user: { type: mongoose.Schema.Types.ObjectId, ref: "User", required: true },
  type: { 
    type: String, 
    enum: ["moodUpdate", "energyUpdate", "coachFeedback"], 
    required: true 
  },
  timestamp: { type: Date, default: Date.now },
  meta: { type: mongoose.Schema.Types.Mixed } // Flexible data payload
});

const Log = mongoose.model("Log", LogSchema);

export default Log;
