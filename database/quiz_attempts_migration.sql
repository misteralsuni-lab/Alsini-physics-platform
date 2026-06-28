-- Migration: Create quiz_attempts table
-- Description: Stores individual question attempts for the Quiz Engine.

CREATE TABLE IF NOT EXISTS public.quiz_attempts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL,
    question_index INTEGER NOT NULL,
    student_answer TEXT,
    score FLOAT,
    max_score INTEGER,
    ai_feedback TEXT,
    last_question_index INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable Row Level Security
ALTER TABLE public.quiz_attempts ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only select their own attempts
CREATE POLICY "Users can view their own quiz attempts" 
    ON public.quiz_attempts 
    FOR SELECT 
    USING (auth.uid() = student_id);

-- Policy: Users can insert their own attempts
CREATE POLICY "Users can insert their own quiz attempts" 
    ON public.quiz_attempts 
    FOR INSERT 
    WITH CHECK (auth.uid() = student_id);

-- Policy: Users can update their own attempts (if needed for resuming/modifying)
CREATE POLICY "Users can update their own quiz attempts" 
    ON public.quiz_attempts 
    FOR UPDATE 
    USING (auth.uid() = student_id);

-- Create an index for faster querying by student and resource
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student_resource 
    ON public.quiz_attempts(student_id, resource_id);
