import Log from "../models/log.models.js";
import User from "../models/user.models.js";

export const createLog = async (req, res) => {
  try {
    const { type, meta, timestamp } = req.body;

    if (!type || !["moodUpdate", "energyUpdate", "coachFeedback"].includes(type)) {
      return res.status(400).json({ error: "Invalid or missing log type." });
    }

    const log = new Log({
      user: req.user._id,
      type,
      meta,
      timestamp: timestamp || new Date()
    });

    await log.save();

    // Update user's currentMood or currentEnergyLevel
    if (type === "moodUpdate" && meta?.mood) {
      await User.findByIdAndUpdate(req.user._id, { currentMood: meta.mood });
    }

    if (type === "energyUpdate" && typeof meta?.energy === "number") {
      await User.findByIdAndUpdate(req.user._id, { currentEnergyLevel: meta.energy });
    }

    res.status(201).json({ success: true, log });
  } catch (error) {
    console.error("❌ Error logging event:", error.message);
    res.status(500).json({ error: "Failed to create log" });
  }
};
