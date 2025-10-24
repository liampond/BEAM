#!/usr/bin/env python3
"""
Generate benchmark questions for 1-bar passages.

This script creates verified questions that:
1. Test format parsing ability
2. Have objective answers
3. Give same answer across all formats
4. Are not easily guessable without looking at the score
"""

from add_question import create_question

# List of proposed questions for review
# Each entry: (sonata, mvmt, measure, question, answer, difficulty, type, notes)

PROPOSED_QUESTIONS = [
    # ========================================================================
    # SONATA 16, MOVEMENT 1, MEASURE 1
    # RH: 2cc (half note), 4ee (quarter), 4gg (quarter)
    # LH: 8cL 8g 8e 8gJ 8cL 8g 8e 8gJ (8 eighth notes)
    # ========================================================================
    (16, 1, 1, 
     "How many notes are in the left hand in this measure?",
     "8",
     "easy", "rhythmic",
     "Counts eighth notes in Alberti bass pattern"),
    
    (16, 1, 1,
     "How many notes are in the right hand in this measure?",
     "3",
     "easy", "rhythmic",
     "Counts half note + 2 quarters"),
    
    (16, 1, 1,
     "What is the pitch of the first note in the right hand (include octave)?",
     "C5",
     "easy", "melodic",
     "First RH note is C5 (2cc in Humdrum)"),
    
    (16, 1, 1,
     "What is the pitch of the lowest note in the left hand (include octave)?",
     "C4",
     "easy", "melodic",
     "Alberti bass pattern uses C4 as lowest pitch"),
    
    (16, 1, 1,
     "What is the duration of the longest note in this measure?",
     "Half note",
     "easy", "rhythmic",
     "First RH note is a half note"),
    
    (16, 1, 1,
     "What is the duration of the longest note in this measure (in beats)?",
     "2",
     "easy", "rhythmic",
     "Alternative duration question - 2 beats in 4/4"),
    
    (16, 1, 1,
     "On which beat does the pitch E5 first appear in the right hand?",
     "3",
     "easy", "general",
     "E5 (4ee) appears on beat 3"),
    
    (16, 1, 1,
     "How many different pitch classes are used in the left hand?",
     "3",
     "easy", "melodic",
     "LH uses C, E, G (3 pitch classes)"),
    
    (16, 1, 1,
     "What is the interval between the first and last notes of the right hand?",
     "Perfect fifth",
     "easy", "melodic",
     "C5 to G5 is a perfect fifth"),
    
    (16, 1, 1,
     "What is the interval in semitones between the first and last notes of the right hand?",
     "7",
     "easy", "melodic",
     "Alternative interval question - C to G is 7 semitones"),
    
    # ========================================================================
    # SONATA 16, MOVEMENT 1, MEASURE 2
    # RH: (4.b, 16ccLL 16ddJJ), 4cc, 4r
    # LH: 8dL 8g 8f 8gJ 8cL 8g 8e 8gJ
    # ========================================================================
    (16, 1, 2,
     "How many rests are in this measure?",
     "1",
     "easy", "rhythmic",
     "One quarter rest in RH"),
    
    (16, 1, 2,
     "What is the pitch of the highest note in the right hand (include octave)?",
     "D5",
     "easy", "melodic",
     "D5 (16dd) is the highest pitch"),
    
    (16, 1, 2,
     "How many sixteenth notes appear in the right hand?",
     "2",
     "easy", "rhythmic",
     "Two sixteenth notes: C5 and D5"),
    
    (16, 1, 2,
     "What is the duration of the first note in the right hand?",
     "Dotted quarter note",
     "easy", "rhythmic",
     "First RH note is dotted quarter (4.b)"),
    
    (16, 1, 2,
     "What is the duration of the first note in the right hand (in beats)?",
     "1.5",
     "easy", "rhythmic",
     "Alternative - dotted quarter = 1.5 beats"),
    
    # ========================================================================
    # SONATA 16, MOVEMENT 1, MEASURE 3
    # RH: 2aa, 4gg, 4ccc
    # LH: 8cL 8a 8f 8aJ 8cL 8g 8e 8gJ
    # ========================================================================
    (16, 1, 3,
     "What is the pitch of the first note in the left hand (include octave)?",
     "C4",
     "easy", "melodic",
     "First LH note is C4"),
    
    (16, 1, 3,
     "What is the pitch of the highest note in the right hand (include octave)?",
     "C6",
     "easy", "melodic",
     "C6 (4ccc) is the highest"),
    
    (16, 1, 3,
     "How many half notes are in this measure?",
     "1",
     "easy", "rhythmic",
     "Only the first RH note (2aa) is a half note"),
    
    (16, 1, 3,
     "How many different pitch classes are used in the right hand?",
     "3",
     "easy", "melodic",
     "RH uses A, G, C (3 pitch classes)"),
    
    # ========================================================================
    # SONATA 13, MOVEMENT 2, MEASURE 11
    # More complex - has split voices in RH
    # Skip for now - too complex for 1-bar questions
    # ========================================================================
    
    # ========================================================================
    # SONATA 1, MOVEMENT 1, MEASURE 1
    # Need to verify this one
    # ========================================================================
]


def generate_questions():
    """Generate all proposed questions."""
    print("\n" + "="*80)
    print("GENERATING BENCHMARK QUESTIONS - 1-BAR PASSAGES")
    print("="*80)
    print(f"\nTotal questions proposed: {len(PROPOSED_QUESTIONS)}\n")
    
    for i, (sonata, mvmt, measure, question, answer, difficulty, qtype, notes) in enumerate(PROPOSED_QUESTIONS, 1):
        print(f"\n{'='*80}")
        print(f"QUESTION {i}/{len(PROPOSED_QUESTIONS)}")
        print(f"{'='*80}")
        print(f"Sonata: {sonata}, Movement: {mvmt}, Measure: {measure}")
        print(f"Q: {question}")
        print(f"A: {answer}")
        print(f"Difficulty: {difficulty}, Type: {qtype}")
        print(f"Notes: {notes}")
        print(f"{'='*80}")
        
        response = input("\n Add this question? (y/n/skip all): ").strip().lower()
        
        if response == 'skip all':
            print("\nStopping question generation.")
            break
        elif response == 'y':
            try:
                create_question(
                    sonata_number=sonata,
                    movement=mvmt,
                    start_measure=measure,
                    end_measure=measure,
                    question_text=question,
                    correct_answer=answer,
                    granularity="bar",
                    difficulty=difficulty,
                    question_type=qtype
                )
            except Exception as e:
                print(f"❌ Error creating question: {e}")
        else:
            print("⏭️  Skipped")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        # Auto-add all questions without prompting
        for sonata, mvmt, measure, question, answer, difficulty, qtype, notes in PROPOSED_QUESTIONS:
            create_question(
                sonata_number=sonata,
                movement=mvmt,
                start_measure=measure,
                end_measure=measure,
                question_text=question,
                correct_answer=answer,
                granularity="bar",
                difficulty=difficulty,
                question_type=qtype
            )
    else:
        generate_questions()
