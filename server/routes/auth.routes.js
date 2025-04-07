import express from 'express';
import {signup, login, logout, getMe} from '../controllers/auth.controllers.js';
import protectRoute from '../middleware/protectRoute.middleware.js';

const authRouter = express.Router();

authRouter.get("/getme", protectRoute, getMe); //protectRoute is a middleware
authRouter.post("/signup", signup);
authRouter.get("/login", login);
authRouter.get("/logout", logout);

export default authRouter;