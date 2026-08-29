// Shared Data Contract
export interface LearnerProfile {
  resumeText?: string;
  existingSkills: string[];
  projects: { title: string; techStack: string[]; description: string }[];
  targetRole: string;
}

export interface SkillGapAnalysis {
  matchPercentage: number;
  criticalGaps: string[];  // Red
  developingSkills: string[]; // Yellow
  strongSkills: string[];   // Green
}

export interface RoadmapStep {
  id: string;
  stepNumber: number;
  title: string;
  actionType: 'Learn' | 'Practice' | 'Build' | 'Validate';
  description: string;
  recommendedResource: string;
  isCompleted: boolean;
}

export interface PathForgeResponse {
  skillGap: SkillGapAnalysis;
  roadmap: RoadmapStep[];
}
