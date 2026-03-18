import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabaseClient';
import { LogIn, UserPlus, Mail, Lock, Eye, EyeOff, AlertCircle, X, KeyRound } from 'lucide-react';
import gsap from 'gsap';

const Auth = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [isResetPassword, setIsResetPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  
  const [emailFocused, setEmailFocused] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);
  
  const navigate = useNavigate();

  const containerRef = useRef(null);
  const formRef = useRef(null);
  const errorRef = useRef(null);
  
  // Entrance Animation
  useEffect(() => {
    gsap.fromTo(
      containerRef.current,
      { opacity: 0, y: 40 },
      { opacity: 1, y: 0, duration: 1, ease: 'power3.out' }
    );
  }, []);

  // Mode Switch Animation
  useEffect(() => {
    if (formRef.current) {
      gsap.fromTo(
        formRef.current,
        { opacity: 0, x: isLogin ? -20 : 20 },
        { opacity: 1, x: 0, duration: 0.5, ease: 'power2.out' }
      );
    }
  }, [isLogin, isResetPassword]);

  // Error Shake Animation
  useEffect(() => {
    if (error && containerRef.current) {
      gsap.fromTo(
        containerRef.current,
        { x: -10 },
        { x: 0, duration: 0.4, ease: 'elastic.out(1, 0.3)', clearProps: 'x' }
      );
    }
  }, [error]);

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);

    try {
      if (isResetPassword) {
        const { error } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/update-password`,
        });
        if (error) throw error;
        setMessage('Check your email for the password reset link!');
      } else if (isLogin) {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        setMessage('Check your email for the confirmation link!');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleResetPassword = () => {
    setIsResetPassword(!isResetPassword);
    setError(null);
    setMessage(null);
  };

  return (
    <div className="flex items-center justify-center min-h-[80vh] px-4 py-12 relative overflow-hidden">
      {/* Background Cinematic Glows */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent-purple/20 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent-cyan/20 rounded-full blur-[120px] pointer-events-none"></div>

      <div ref={containerRef} className="w-full max-w-md relative group z-10">
        {/* Glow Effect around card */}
        <div className="absolute -inset-1 bg-gradient-to-r from-accent-purple/40 to-accent-cyan/40 rounded-3xl blur-md opacity-30 group-hover:opacity-60 transition duration-700"></div>
        
        {/* Glassmorphic Card */}
        <div className="relative bg-zinc-950/60 backdrop-blur-2xl border border-white/10 p-8 sm:p-10 rounded-3xl shadow-2xl">
          
          {/* Close Button */}
          <button
            onClick={() => navigate('/')}
            className="absolute top-4 right-4 p-2 text-zinc-500 hover:text-white bg-white/5 hover:bg-white/10 rounded-full transition-all duration-300 hover:shadow-[0_0_15px_rgba(168,85,247,0.4)] group/close"
            aria-label="Close"
          >
            <X size={20} className="group-hover:scale-110 transition-transform duration-300" />
          </button>

          <div ref={formRef}>
            <div className="text-center mb-10">
              <h2 className="text-3xl font-bold text-white tracking-tight mb-2">
                {isResetPassword ? 'Reset Password' : (isLogin ? 'Student Login' : 'Register Account')}
              </h2>
              <p className="text-zinc-400 text-sm">
                {isResetPassword 
                  ? 'We will send a recovery link to your email' 
                  : (isLogin ? 'Access your physics dashboard' : 'Create your student account')}
              </p>
            </div>

            <form onSubmit={handleAuth} className="space-y-6">
              <div className="space-y-5">
                {/* Email Input */}
                <div className="relative group/input">
                  <div className={`absolute -inset-0.5 bg-gradient-to-r from-accent-cyan to-accent-purple rounded-xl blur opacity-0 transition duration-500 ${emailFocused ? 'opacity-50' : ''}`}></div>
                  <div className="relative">
                    <Mail className={`absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 transition-colors duration-300 ${emailFocused ? 'text-accent-cyan' : 'text-zinc-500'}`} />
                    <input
                      type="email"
                      placeholder="Email Address"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      onFocus={() => setEmailFocused(true)}
                      onBlur={() => setEmailFocused(false)}
                      className="w-full bg-zinc-900/80 border border-white/5 rounded-xl py-3.5 pl-12 pr-4 text-white placeholder:text-zinc-600 focus:outline-none focus:border-transparent transition-all duration-300 shadow-inner"
                      required
                    />
                  </div>
                </div>

                {/* Password Input (Hidden during reset) */}
                {!isResetPassword && (
                  <div className="relative group/input">
                    <div className={`absolute -inset-0.5 bg-gradient-to-r from-accent-purple to-accent-cyan rounded-xl blur opacity-0 transition duration-500 ${passwordFocused ? 'opacity-50' : ''}`}></div>
                    <div className="relative">
                      <Lock className={`absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 transition-colors duration-300 ${passwordFocused ? 'text-accent-purple' : 'text-zinc-500'}`} />
                      <input
                        type={showPassword ? "text" : "password"}
                        placeholder="Password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        onFocus={() => setPasswordFocused(true)}
                        onBlur={() => setPasswordFocused(false)}
                        className="w-full bg-zinc-900/80 border border-white/5 rounded-xl py-3.5 pl-12 pr-12 text-white placeholder:text-zinc-600 focus:outline-none focus:border-transparent transition-all duration-300 shadow-inner"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white transition duration-200"
                      >
                        {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Forgot Password Link */}
              {isLogin && !isResetPassword && (
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={toggleResetPassword}
                    className="text-sm text-zinc-500 hover:text-accent-cyan transition-colors duration-200"
                  >
                    Forgot Password?
                  </button>
                </div>
              )}

              {/* Error Message */}
              {error && (
                <div ref={errorRef} className="flex items-start gap-3 p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm backdrop-blur-md">
                  <AlertCircle className="w-5 h-5 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Success Message */}
              {message && (
                <div className="flex items-start gap-3 p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm backdrop-blur-md">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 mt-1.5 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]"></div>
                  <span>{message}</span>
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading}
                className="relative w-full group overflow-hidden bg-zinc-900 border border-white/10 text-white font-semibold py-3.5 rounded-xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 hover:border-transparent"
              >
                <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-accent-purple to-accent-cyan opacity-80 group-hover:opacity-100 transition-opacity duration-300"></div>
                <div className="relative flex items-center gap-2 z-10 drop-shadow-md">
                  {loading ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  ) : (
                    <>
                      {isResetPassword ? <KeyRound size={20} /> : (isLogin ? <LogIn size={20} /> : <UserPlus size={20} />)}
                      {isResetPassword ? 'Send Recovery Link' : (isLogin ? 'Login' : 'Create Account')}
                    </>
                  )}
                </div>
              </button>
            </form>

            <div className="mt-8 pt-6 border-t border-white/10 text-center">
              {isResetPassword ? (
                <button
                  type="button"
                  onClick={toggleResetPassword}
                  className="text-zinc-400 hover:text-white text-sm transition duration-300 hover:underline decoration-white/30 underline-offset-4"
                >
                  Back to Login
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setIsLogin(!isLogin)}
                  className="text-zinc-400 hover:text-white text-sm transition duration-300 hover:underline decoration-white/30 underline-offset-4"
                >
                  {isLogin ? "Don't have an account? Create one" : "Already registered? Log in"}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Auth;
