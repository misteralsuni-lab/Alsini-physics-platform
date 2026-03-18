import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabaseClient';
import { Lock, Eye, EyeOff, AlertCircle, X, CheckCircle } from 'lucide-react';
import gsap from 'gsap';

const UpdatePassword = () => {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  
  const [pwFocused, setPwFocused] = useState(false);
  const [confirmPwFocused, setConfirmPwFocused] = useState(false);
  
  const navigate = useNavigate();

  const containerRef = useRef(null);
  const formRef = useRef(null);

  // Entrance Animation
  useEffect(() => {
    gsap.fromTo(
      containerRef.current,
      { opacity: 0, y: 40 },
      { opacity: 1, y: 0, duration: 1, ease: 'power3.out' }
    );
  }, []);

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

  const handleUpdatePassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      setLoading(false);
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      setLoading(false);
      return;
    }

    try {
      const { error } = await supabase.auth.updateUser({
        password: password
      });

      if (error) throw error;
      
      setMessage('Password updated successfully. Rerouting to dashboard...');
      
      // Give them a moment to read the success message before navigating away
      setTimeout(() => {
        navigate('/');
      }, 2000);

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-[80vh] px-4 py-12 relative overflow-hidden">
      {/* Background Cinematic Glows */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent-purple/20 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent-cyan/20 rounded-full blur-[120px] pointer-events-none"></div>

      <div ref={containerRef} className="w-full max-w-md relative group z-10">
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
                Secure Update
              </h2>
              <p className="text-zinc-400 text-sm">
                Enter your new private access key below.
              </p>
            </div>

            <form onSubmit={handleUpdatePassword} className="space-y-6">
              <div className="space-y-5">
                
                {/* New Password Input */}
                <div className="relative group/input">
                  <div className={`absolute -inset-0.5 bg-gradient-to-r from-accent-purple to-accent-cyan rounded-xl blur opacity-0 transition duration-500 ${pwFocused ? 'opacity-50' : ''}`}></div>
                  <div className="relative">
                    <Lock className={`absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 transition-colors duration-300 ${pwFocused ? 'text-accent-purple' : 'text-zinc-500'}`} />
                    <input
                      type={showPassword ? "text" : "password"}
                      placeholder="New Password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      onFocus={() => setPwFocused(true)}
                      onBlur={() => setPwFocused(false)}
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

                {/* Confirm Password Input */}
                <div className="relative group/input">
                  <div className={`absolute -inset-0.5 bg-gradient-to-r from-accent-cyan to-accent-purple rounded-xl blur opacity-0 transition duration-500 ${confirmPwFocused ? 'opacity-50' : ''}`}></div>
                  <div className="relative">
                    <CheckCircle className={`absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 transition-colors duration-300 ${confirmPwFocused ? 'text-accent-cyan' : 'text-zinc-500'}`} />
                    <input
                      type={showPassword ? "text" : "password"}
                      placeholder="Confirm New Password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      onFocus={() => setConfirmPwFocused(true)}
                      onBlur={() => setConfirmPwFocused(false)}
                      className="w-full bg-zinc-900/80 border border-white/5 rounded-xl py-3.5 pl-12 pr-12 text-white placeholder:text-zinc-600 focus:outline-none focus:border-transparent transition-all duration-300 shadow-inner"
                      required
                    />
                  </div>
                </div>

              </div>

              {/* Error Message */}
              {error && (
                <div className="flex items-start gap-3 p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm backdrop-blur-md">
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
                      <Lock size={20} />
                      Set New Password
                    </>
                  )}
                </div>
              </button>
            </form>

          </div>
        </div>
      </div>
    </div>
  );
};

export default UpdatePassword;
