// Preset rubrics for different types of essays
const presetRubrics = [
  {
    id: 'argumentative',
    name: 'Argumentative Essay Rubric',
    content: `Argumentative Essay Evaluation Rubric:

1. Thesis & Position (0-6):
   - Clear, debatable thesis statement
   - Strong position on the issue
   - Thesis addresses complexity of the topic

2. Evidence & Support (0-6):
   - Relevant, credible evidence
   - Multiple types of evidence (statistics, examples, expert opinions)
   - Evidence directly supports the argument

3. Counterarguments & Rebuttals (0-6):
   - Acknowledges opposing viewpoints
   - Addresses counterarguments fairly
   - Provides effective rebuttals

4. Organization & Structure (0-4):
   - Logical progression of ideas
   - Effective introduction and conclusion
   - Clear transitions between paragraphs

5. Persuasive Techniques (0-4):
   - Effective use of rhetorical strategies
   - Appeals to logic, emotion, and ethics
   - Compelling and persuasive language

6. Grammar & Mechanics (0-4):
   - Correct grammar, spelling, and punctuation
   - Varied sentence structure
   - Academic tone and language`
  },
  {
    id: 'narrative',
    name: 'Narrative Essay Rubric',
    content: `Narrative Essay Evaluation Rubric:

1. Storytelling & Plot (0-6):
   - Engaging and well-developed plot
   - Clear beginning, middle, and end
   - Purposeful narrative arc

2. Character Development (0-6):
   - Well-developed main character(s)
   - Authentic dialogue and interactions
   - Character growth or insight

3. Setting & Description (0-6):
   - Vivid sensory details
   - Effective use of descriptive language
   - Setting enhances the story

4. Theme & Purpose (0-4):
   - Clear central message or theme
   - Theme is developed throughout the narrative
   - Meaningful conclusion or insight

5. Voice & Style (0-4):
   - Distinctive narrative voice
   - Appropriate tone for the story
   - Creative and engaging language

6. Grammar & Mechanics (0-4):
   - Correct grammar, spelling, and punctuation
   - Varied sentence structure
   - Appropriate dialogue formatting`
  },
  {
    id: 'analytical',
    name: 'Analytical Essay Rubric',
    content: `Analytical Essay Evaluation Rubric:

1. Thesis & Analysis (0-6):
   - Clear analytical thesis
   - Insightful interpretation of the subject
   - Thesis addresses complexity and nuance

2. Evidence & Textual Support (0-6):
   - Relevant textual evidence or examples
   - Effective integration of quotes/examples
   - Evidence directly supports analysis

3. Critical Thinking (0-6):
   - Depth of analysis beyond surface level
   - Consideration of multiple perspectives
   - Original insights and interpretations

4. Organization & Structure (0-4):
   - Logical progression of ideas
   - Clear paragraph structure with topic sentences
   - Effective introduction and conclusion

5. Connection to Broader Context (0-4):
   - Links analysis to wider themes or issues
   - Considers historical, cultural, or theoretical context
   - Demonstrates significance of the analysis

6. Grammar & Academic Style (0-4):
   - Correct grammar, spelling, and punctuation
   - Appropriate academic tone
   - Precise vocabulary and language`
  },
  {
    id: 'research',
    name: 'Research Paper Rubric',
    content: `Research Paper Evaluation Rubric:

1. Research Question & Thesis (0-6):
   - Clear, focused research question
   - Well-developed thesis based on research
   - Thesis demonstrates significance of the research

2. Research Quality (0-6):
   - Diverse, credible sources
   - Appropriate number of sources for topic
   - Current and relevant research

3. Analysis & Synthesis (0-6):
   - Effective integration of sources
   - Critical evaluation of research
   - Synthesis of multiple perspectives

4. Methodology (0-4):
   - Appropriate research methods
   - Clear explanation of methodology
   - Limitations addressed

5. Organization & Structure (0-4):
   - Logical progression of ideas
   - Effective introduction and conclusion
   - Clear section headings and transitions

6. Citations & Formatting (0-4):
   - Correct citation format (APA, MLA, Chicago, etc.)
   - Proper in-text citations
   - Complete and accurate bibliography/works cited`
  },
  {
    id: 'compare-contrast',
    name: 'Compare & Contrast Essay Rubric',
    content: `Compare & Contrast Essay Evaluation Rubric:

1. Thesis & Purpose (0-6):
   - Clear thesis identifying subjects being compared
   - Establishes purpose and significance of comparison
   - Identifies specific points of comparison

2. Organization & Structure (0-6):
   - Effective organizational pattern (point-by-point or subject-by-subject)
   - Balanced treatment of subjects
   - Logical progression of comparisons

3. Comparison Points (0-6):
   - Meaningful points of comparison/contrast
   - Depth of analysis for each comparison point
   - Insightful connections between subjects

4. Evidence & Support (0-4):
   - Relevant evidence for each comparison
   - Specific details and examples
   - Evidence directly supports comparisons

5. Transitions & Connections (0-4):
   - Clear transitional phrases for comparisons
   - Effective linking of similar/different aspects
   - Cohesive overall structure

6. Grammar & Style (0-4):
   - Correct grammar, spelling, and punctuation
   - Varied sentence structure
   - Appropriate academic tone`
  }
];

export default presetRubrics; 