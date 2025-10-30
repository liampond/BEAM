#!/usr/bin/env python3
"""
Simplified interface for adding questions to the benchmark database.

This script combines passage creation, question creation, and test case generation
into a single workflow.
"""

import sys
from typing import List, Tuple
from db_utils import (
    get_piece_id, add_passage, add_question,
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


def interactive_add():
    """Interactive mode for adding questions."""
    print("\n" + "="*70)
    print("INTERACTIVE QUESTION CREATOR")
    print("="*70 + "\n")
    
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
    correct_answer = input("Correct answer: ")
    
    # Get difficulty and type
    print("\nDifficulty options: easy, medium, hard")
    difficulty = input("Difficulty [medium]: ").strip() or "medium"
    
    print("\nQuestion type options: general, harmonic, melodic, rhythmic, formal")
    question_type = input("Question type [general]: ").strip() or "general"
    
    # Optional passage description
    passage_desc = input("\nPassage description (optional): ").strip() or None
    
    # Create the question
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
        print("\nOr import and use create_question() in Python:\n")
        print("  from add_question import create_question")
        print("\n  create_question(")
        print("      sonata_number=16, movement=1,")
        print("      start_measure=1, end_measure=4,")
        print("      question_text='What is the key of this passage?',")
        print("      correct_answer='C major',")
        print("      granularity='phrase',")
        print("      difficulty='easy',")
        print("      question_type='harmonic'")
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
