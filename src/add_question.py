#!/usr/bin/env python3
"""
Simplified interface for adding questions to the benchmark database.

This script combines passage creation, question creation, and test case generation
into a single workflow.
"""

import sys
from typing import List, Tuple
from db_utils import (
    get_piece_id, add_passage, add_question, add_multiple_choice_question,
    create_test_cases, list_passages, list_questions, show_stats
)


def create_question(sonata_number: int, movement: int, 
                   start_measure: int, end_measure: int,
                   question_text: str, correct_answer: str,
                   granularity: str = "bar",
                   difficulty: str = "medium",
                   question_type: str = "general",
                   passage_description: str = None) -> tuple:
    """
    Create a complete question with passage and test cases.
    
    Args:
        sonata_number: Sonata number (1-18)
        movement: Movement number (1-3)
        start_measure: First measure of passage
        end_measure: Last measure of passage (same as start for single measure)
        question_text: The question to ask
        correct_answer: The correct answer
        granularity: One of: bar, phrase, section, movement
        difficulty: One of: easy, medium, hard
        question_type: One of: general, harmonic, melodic, rhythmic, formal
        passage_description: Optional description of the passage
    
    Returns:
        Tuple of (passage_id, question_id, test_case_count)
    """
    # Validate inputs
    if not get_piece_id(sonata_number, movement):
        raise ValueError(f"No piece found for Sonata {sonata_number}, Movement {movement}")
    
    valid_granularities = ["bar", "phrase", "section", "movement"]
    if granularity not in valid_granularities:
        raise ValueError(f"Granularity must be one of: {valid_granularities}")
    
    valid_difficulties = ["easy", "medium", "hard"]
    if difficulty not in valid_difficulties:
        raise ValueError(f"Difficulty must be one of: {valid_difficulties}")
    
    valid_types = ["general", "harmonic", "melodic", "rhythmic", "formal"]
    if question_type not in valid_types:
        raise ValueError(f"Question type must be one of: {valid_types}")
    
    # Auto-generate passage description if not provided
    if passage_description is None:
        measure_desc = f"measure {start_measure}" if start_measure == end_measure else f"measures {start_measure}-{end_measure}"
        passage_description = f"Sonata {sonata_number}, Movement {movement}, {measure_desc}"
    
    print(f"\n{'='*70}")
    print(f"CREATING QUESTION")
    print(f"{'='*70}")
    print(f"Piece: Sonata {sonata_number}, Movement {movement}")
    print(f"Passage: mm. {start_measure}-{end_measure} ({granularity})")
    print(f"Question: {question_text}")
    print(f"Answer: {correct_answer}")
    print(f"Difficulty: {difficulty}, Type: {question_type}")
    print(f"{'='*70}\n")
    
    # Create passage
    passage_id = add_passage(
        sonata_number, movement, start_measure, end_measure, 
        passage_description, granularity
    )
    
    # Create question
    question_id = add_question(
        passage_id, question_text, correct_answer,
        difficulty, question_type
    )
    
    # Create test cases for all formats
    test_count = create_test_cases(question_id)
    
    print(f"\n{'='*70}")
    print(f"✅ COMPLETE: Question {question_id} created with {test_count} test cases")
    print(f"{'='*70}\n")
    
    return passage_id, question_id, test_count


def create_multiple_choice_question(sonata_number: int, movement: int,
                                    start_measure: int, end_measure: int,
                                    question_text: str, 
                                    choices: List[Tuple[str, bool]],
                                    granularity: str = "bar",
                                    difficulty: str = "medium",
                                    question_type: str = "general",
                                    passage_description: str = None) -> tuple:
    """
    Create a multiple choice question with passage and test cases.
    
    Args:
        sonata_number: Sonata number (1-18)
        movement: Movement number (1-3)
        start_measure: First measure of passage
        end_measure: Last measure of passage (same as start for single measure)
        question_text: The question to ask
        choices: List of exactly 4 (choice_text, is_correct) tuples. Exactly one must be correct.
                 The correct answer will be randomly assigned to A, B, C, or D.
        granularity: One of: bar, phrase, section, movement
        difficulty: One of: easy, medium, hard
        question_type: One of: general, harmonic, melodic, rhythmic, formal
        passage_description: Optional description of the passage
    
    Returns:
        Tuple of (passage_id, question_id, test_case_count)
    """
    # Validate inputs
    if not get_piece_id(sonata_number, movement):
        raise ValueError(f"No piece found for Sonata {sonata_number}, Movement {movement}")
    
    if len(choices) != 4:
        raise ValueError(f"Must provide exactly 4 choices, got {len(choices)}")
    
    valid_granularities = ["bar", "phrase", "section", "movement"]
    if granularity not in valid_granularities:
        raise ValueError(f"Granularity must be one of: {valid_granularities}")
    
    valid_difficulties = ["easy", "medium", "hard"]
    if difficulty not in valid_difficulties:
        raise ValueError(f"Difficulty must be one of: {valid_difficulties}")
    
    valid_types = ["general", "harmonic", "melodic", "rhythmic", "formal"]
    if question_type not in valid_types:
        raise ValueError(f"Question type must be one of: {valid_types}")
    
    # Auto-generate passage description if not provided
    if passage_description is None:
        measure_desc = f"measure {start_measure}" if start_measure == end_measure else f"measures {start_measure}-{end_measure}"
        passage_description = f"Sonata {sonata_number}, Movement {movement}, {measure_desc}"
    
    # Get correct answer for display
    correct_answer = next((text for text, is_correct in choices if is_correct), "Unknown")
    
    print(f"\n{'='*70}")
    print(f"CREATING MULTIPLE CHOICE QUESTION")
    print(f"{'='*70}")
    print(f"Piece: Sonata {sonata_number}, Movement {movement}")
    print(f"Passage: mm. {start_measure}-{end_measure} ({granularity})")
    print(f"Question: {question_text}")
    print(f"Choices (will be randomized to A/B/C/D):")
    for i, (choice_text, is_correct) in enumerate(choices, 1):
        marker = "✓" if is_correct else " "
        print(f"  {marker} {i}. {choice_text}")
    print(f"Difficulty: {difficulty}, Type: {question_type}")
    print(f"{'='*70}\n")
    
    # Create passage
    passage_id = add_passage(
        sonata_number, movement, start_measure, end_measure, 
        passage_description, granularity
    )
    
    # Create multiple choice question (will randomize internally)
    question_id = add_multiple_choice_question(
        passage_id, question_text, choices,
        difficulty, question_type
    )
    
    # Create test cases for all formats
    test_count = create_test_cases(question_id)
    
    print(f"\n{'='*70}")
    print(f"✅ COMPLETE: Question {question_id} created with 4 choices (A/B/C/D) and {test_count} test cases")
    print(f"{'='*70}\n")
    
    return passage_id, question_id, test_count


def interactive_add():
    """Interactive mode for adding questions."""
    print("\n" + "="*70)
    print("INTERACTIVE QUESTION CREATOR")
    print("="*70 + "\n")
    
    # Ask if multiple choice
    mc_input = input("Multiple choice question? (y/n) [n]: ").strip().lower()
    is_multiple_choice = mc_input in ['y', 'yes']
    
    # Get piece info
    sonata = int(input("Sonata number (1-18): "))
    movement = int(input("Movement number (1-3): "))
    
    # Get passage info
    start_measure = int(input("Start measure: "))
    end_measure_input = input(f"End measure (or press Enter for {start_measure}): ")
    end_measure = int(end_measure_input) if end_measure_input else start_measure
    
    # Get granularity
    print("\nGranularity options: bar, phrase, section, movement")
    granularity = input("Granularity [bar]: ").strip() or "bar"
    
    # Get question
    print("\n" + "-"*70)
    question_text = input("Question text: ")
    
    if is_multiple_choice:
        # Get multiple choice answers
        print("\nEnter exactly 4 answer choices. Mark the correct answer with an asterisk (*).")
        print("The correct answer will be randomly assigned to A, B, C, or D.")
        print("Example: *C major    (correct answer)")
        print("         C minor    (distractor)")
        print("         G major    (distractor)")
        print("         F major    (distractor)\n")
        
        choices = []
        for choice_num in range(1, 5):
            while True:
                choice_input = input(f"Choice {choice_num}: ").strip()
                if not choice_input:
                    print("Choice cannot be empty. Please enter a choice.")
                    continue
                
                # Check if marked as correct
                if choice_input.startswith('*'):
                    choice_text = choice_input[1:].strip()
                    is_correct = True
                else:
                    choice_text = choice_input
                    is_correct = False
                
                choices.append((choice_text, is_correct))
                break
        
        # Validate exactly one correct answer
        correct_count = sum(1 for _, is_correct in choices if is_correct)
        if correct_count != 1:
            print(f"\nError: Must have exactly 1 correct answer, but found {correct_count}")
            return
    else:
        # Get single correct answer
        correct_answer = input("Correct answer: ")
    
    # Get difficulty and type
    print("\nDifficulty options: easy, medium, hard")
    difficulty = input("Difficulty [medium]: ").strip() or "medium"
    
    print("\nQuestion type options: general, harmonic, melodic, rhythmic, formal")
    question_type = input("Question type [general]: ").strip() or "general"
    
    # Optional passage description
    passage_desc = input("\nPassage description (optional): ").strip() or None
    
    # Create the question
    if is_multiple_choice:
        create_multiple_choice_question(
            sonata, movement, start_measure, end_measure,
            question_text, choices,
            granularity, difficulty, question_type, passage_desc
        )
    else:
        create_question(
            sonata, movement, start_measure, end_measure,
            question_text, correct_answer,
            granularity, difficulty, question_type, passage_desc
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python add_question.py interactive")
        print("  python add_question.py list")
        print("  python add_question.py stats")
        print("\nOr import and use create_question() or create_multiple_choice_question() in Python:\n")
        print("  from add_question import create_question, create_multiple_choice_question")
        print("\n  # Simple question:")
        print("  create_question(")
        print("      sonata_number=16, movement=1,")
        print("      start_measure=1, end_measure=4,")
        print("      question_text='What is the key of this passage?',")
        print("      correct_answer='C major',")
        print("      granularity='phrase',")
        print("      difficulty='easy',")
        print("      question_type='harmonic'")
        print("  )")
        print("\n  # Multiple choice question:")
        print("  create_multiple_choice_question(")
        print("      sonata_number=16, movement=1,")
        print("      start_measure=1, end_measure=1,")
        print("      question_text='What is the time signature?',")
        print("      choices=[")
        print("          ('4/4', True),   # Correct answer (will be randomized to A/B/C/D)")
        print("          ('3/4', False),  # Distractor")
        print("          ('2/4', False),  # Distractor")
        print("          ('6/8', False),  # Distractor")
        print("      ],")
        print("      difficulty='easy',")
        print("      question_type='rhythmic'")
        print("  )")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "interactive":
        interactive_add()
    elif command == "list":
        list_passages()
        list_questions()
    elif command == "stats":
        show_stats()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
