import express from "express";
import {
  signup,
  login,
  logout,
  getMe
} from "../controllers/auth.controllers.js";
import protectRoute from "../middleware/protectRoute.middleware.js";

const authRouter = express.Router();

// Authentication Routes
authRouter.post("/signup", signup);
authRouter.get("/login", login);
authRouter.get("/logout", logout);

// Protected route to fetch authenticated user
authRouter.get("/getme", protectRoute, getMe);

export default authRouter;
