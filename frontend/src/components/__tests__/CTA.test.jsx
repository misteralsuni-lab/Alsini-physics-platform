import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import CTA from '../CTA';

describe('CTA', () => {
  it('renders section headers', () => {
    render(<CTA />);
    expect(screen.getByText('Commence Protocol')).toBeInTheDocument();
    expect(screen.getByText('Select your exam route.')).toBeInTheDocument();
  });

  it('renders IGCSE card with button', () => {
    render(<CTA />);
    expect(screen.getByText('Level 1')).toBeInTheDocument();
    expect(screen.getByText('Edexcel IGCSE')).toBeInTheDocument();
    expect(screen.getByText('Core & Extended Content')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Enter IGCSE Dashboard/i })).toBeInTheDocument();
  });

  it('renders A-Level card with button', () => {
    render(<CTA />);
    expect(screen.getByText('Level 2')).toBeInTheDocument();
    expect(screen.getByText('Edexcel A-Level')).toBeInTheDocument();
    expect(screen.getByText('AS & A2 Modules')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Enter A-Level Dashboard/i })).toBeInTheDocument();
  });
});
