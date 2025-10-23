#!/usr/bin/env python3
"""
Example: Adding questions to the benchmark database.

This script demonstrates how to add passages, questions, and test cases
to the benchmark database using the db_utils helper functions.
"""

from db_utils import (
    add_passage, 
    add_question, 
    create_test_cases,
    list_passages,
    list_questions,
    show_stats
)

def add_example_questions():
    """Add example questions for Sonata 16, Movement 1."""
    
    print("="*60)
    print("ADDING EXAMPLE QUESTIONS")
    print("="*60)
    
    # The passage already exists (created by init_database.py)
    # passage_id = 1: Sonata 16, Movement 1, measures 1-4
    passage_id = 1
    
    print("\nAdding questions for existing passage (ID 1)...\n")
    
    # Example 1: Easy question about time signature
    q1_id = add_question(
        passage_id=passage_id,
        question_text="What is the time signature of this movement?",
        correct_answer="4/4",
        difficulty="easy",
        question_type="notation"
    )
    create_test_cases(q1_id)
    
    # Example 2: Easy question about key signature
    q2_id = add_question(
        passage_id=passage_id,
        question_text="What is the key signature?",
        correct_answer="C major",
        difficulty="easy",
        question_type="notation"
    )
    create_test_cases(q2_id)
    
    # Example 3: Medium question about specific pitch
    q3_id = add_question(
        passage_id=passage_id,
        question_text="What is the first pitch in measure 1 of the right hand?",
        correct_answer="B4",
        difficulty="medium",
        question_type="pitch"
    )
    create_test_cases(q3_id)
    
    print("\n" + "="*60)
    print("EXAMPLE QUESTIONS ADDED")
    print("="*60)
    
    # Show what we created
    print("\n")
    list_questions(passage_id)
    print("\n")
    show_stats()


def add_more_passages():
    """Add more passages for Sonata 16, Movement 1."""
    
    print("\n" + "="*60)
    print("ADDING MORE PASSAGES")
    print("="*60 + "\n")
    
    # Add passage for measure 5 (single bar)
    p1 = add_passage(
        sonata_number=16,
        movement=1,
        start_measure=5,
        end_measure=5,
        description="Single bar - measure 5",
        granularity="bar"
    )
    
    # Add passage for measures 5-8 (phrase)
    p2 = add_passage(
        sonata_number=16,
        movement=1,
        start_measure=5,
        end_measure=8,
        description="Second phrase",
        granularity="phrase"
    )
    
    print("\n")
    list_passages(sonata_number=16, movement=1)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        print("Running example...")
        add_example_questions()
        # Uncomment to add more passages:
        # add_more_passages()
    else:
        print(__doc__)
        print("\nThis is an example script showing how to add questions.")
        print("To actually run it and add example questions, use:")
        print("  python src/example_add_questions.py --run")
        print("\nNote: This will modify your database!")
