#!/usr/bin/env python3
"""
Final optimized assignment algorithm with detailed reasons for unassigned pairs/individuals.
Maximizes total assignments while managing coach workload balance.
"""

import polars as pl
import random
from itertools import combinations
import networkx as nx
from xlsxwriter import Workbook
import os


def load_data(baseline: pl.DataFrame, coach: pl.DataFrame):
    """Load baseline and coach data."""
    return baseline, coach


def setup_randomization(baseline_df, seed):
    """Split participants into partner/individual groups using randomization."""
    random.seed(seed)
    partner = ['partner'] * 28
    individual = ['individual'] * 14
    randomization_list = partner + individual
    random.shuffle(randomization_list)
    
    baseline_df = baseline_df.with_columns(
        pl.Series(randomization_list).alias('randomization')
    )
    
    individuals_df = baseline_df.filter(pl.col('randomization') == 'individual')
    partner_df = baseline_df.filter(pl.col('randomization') == 'partner')
    
    return individuals_df, partner_df


def get_common_partners_per_time(partner_df):
    """Get all pairs of partners available in each time slot."""
    availability_columns = [
        col for col in partner_df.columns
        if col not in ['ID', 'Age', 'Race', 'Steps', 'Availabilty_Prop', 'randomization']
    ]
    rows = []
    for column_name in availability_columns:
        available_ids = (
            partner_df.filter(pl.col(column_name) == 1)
            .get_column('ID')
            .sort()
            .to_list()
        )
        common_partners = [list(pair) for pair in combinations(available_ids, 2)]
        rows.append({
            'time_slot': column_name,
            'common_partners': common_partners,
        })
    return pl.DataFrame(rows)


def calculate_discrepency_score(partner_df, common_partners_df):
    """Calculate discrepancy scores for each pair based on demographics."""
    discrepancy_scores = []
    for row in common_partners_df.iter_rows(named=True):
        row_scores = []
        for pair in row['common_partners']:
            p1, p2 = pair
            p1_age = partner_df.filter(pl.col('ID') == p1).select('Age').item()
            p2_age = partner_df.filter(pl.col('ID') == p2).select('Age').item()
            p1_race = partner_df.filter(pl.col('ID') == p1).select('Race').item()
            p2_race = partner_df.filter(pl.col('ID') == p2).select('Race').item()
            p1_steps = partner_df.filter(pl.col('ID') == p1).select('Steps').item()
            p2_steps = partner_df.filter(pl.col('ID') == p2).select('Steps').item()

            if p1_race == 6 and p2_race == 6:
                score = (0.6 * abs(p1_steps - p2_steps)) + (0.4 * abs(p1_age - p2_age))
            elif p1_race != p2_race:
                score = (0.5 * abs(p1_steps - p2_steps)) + (0.25 * abs(p1_age - p2_age)) + 0.25
            else:
                score = (0.5 * abs(p1_steps - p2_steps)) + (0.25 * abs(p1_age - p2_age))
            row_scores.append(score)
        discrepancy_scores.append(row_scores)
    
    return common_partners_df.with_columns(pl.Series('discrepency_score', discrepancy_scores))


def add_available_coaches(common_partners_df, coach_df):
    """Map coach availability to time slots."""
    coach_lookup = {}
    coach_columns = [col for col in coach_df.columns if col != 'Initials']
    for col in coach_columns:
        available_coaches = coach_df.filter(pl.col(col).cast(pl.Utf8) == '1').get_column('Initials').to_list()
        coach_lookup[col] = available_coaches
    
    available_coaches = [coach_lookup.get(ts, []) for ts in common_partners_df.get_column('time_slot').to_list()]
    return common_partners_df.with_columns(pl.Series('available_coaches', available_coaches))


def add_available_individuals(common_partners_df, individuals_df):
    """Map individual availability to time slots."""
    individual_lookup = {}
    individual_columns = [col for col in individuals_df.columns if col.startswith(('S', 'M', 'T', 'W', 'Th'))]
    for col in individual_columns:
        available_individuals = individuals_df.filter(pl.col(col) == 1).get_column('ID').sort().to_list()
        individual_lookup[col] = available_individuals
    
    available_individuals = [individual_lookup.get(ts, []) for ts in common_partners_df.get_column('time_slot').to_list()]
    return common_partners_df.with_columns(pl.Series('available_individuals', available_individuals))


def assign_participants(common_partners_df, max_pairs=14):
    """
    Assign partners and individuals to time slots.
    Prioritizes total assignments, then uses discrepancy score as tiebreaker.
    """
    slot_taken = {}
    session_counts = {}
    partner_rows = []
    unassigned_pairs = []
    individual_rows = []
    unassigned_individuals = []
    
    # Pre-calculate slot flexibility for prioritization
    slot_coach_counts = {row['time_slot']: len(row.get('available_coaches', [])) 
                         for row in common_partners_df.iter_rows(named=True)}
    
    def available_coaches_for_slot(time_slot, coach_list):
        taken = slot_taken.setdefault(time_slot, set())
        return [c for c in coach_list if c not in taken]
    
    def claim_coach(time_slot, coach_list):
        remaining = available_coaches_for_slot(time_slot, coach_list)
        if not remaining:
            return None
        # Prefer coaches with fewer sessions (load balancing)
        coach = min(remaining, key=lambda c: (session_counts.get(c, 0), c))
        slot_taken[time_slot].add(coach)
        session_counts[coach] = session_counts.get(coach, 0) + 1
        return coach
    
    def sort_key(row):
        # Prioritize slots with more coach options (more flexibility)
        return (-slot_coach_counts.get(row['time_slot'], 0), row['time_slot'])
    
    # Build pair score lookup
    pair_score_lookup = {}
    for row in common_partners_df.iter_rows(named=True):
        for pair, score in zip(row['common_partners'], row['discrepency_score']):
            pair_key = tuple(sorted(pair))
            pair_score_lookup[pair_key] = min(pair_score_lookup.get(pair_key, score), score)
    
    # Find all feasible pairs (with at least one coach-available slot)
    feasible_pairs = {}
    for row in common_partners_df.iter_rows(named=True):
        if row['available_coaches']:
            for pair in row['common_partners']:
                pair_key = tuple(sorted(pair))
                if pair_key not in feasible_pairs:
                    feasible_pairs[pair_key] = {'time_slots': [], 'slot_count': 0}
                feasible_pairs[pair_key]['time_slots'].append(row['time_slot'])
    for pair_key in feasible_pairs:
        feasible_pairs[pair_key]['slot_count'] = len(feasible_pairs[pair_key]['time_slots'])
    
    # Sort pairs by scarcity (fewer options first), then by discrepancy
    sorted_pairs = sorted(
        list(feasible_pairs.keys()),
        key=lambda p: (feasible_pairs[p]['slot_count'], pair_score_lookup.get(p, 999))
    )
    
    # Build bipartite graph for optimal matching
    graph = nx.Graph()
    for p1, p2 in sorted_pairs:
        graph.add_edge(p1, p2, weight=pair_score_lookup.get((p1, p2), 999))
    
    # Get min-weight matching (prioritizes similar demographic pairs)
    matching = nx.algorithms.matching.min_weight_matching(graph, weight='weight')
    matched_pairs = [sorted(list(p)) for p in matching]
    matched_pairs_sorted = sorted(matched_pairs, key=lambda p: pair_score_lookup.get(tuple(sorted(p)), 999))
    
    # Assign coaches to pairs
    for p1, p2 in matched_pairs_sorted[:max_pairs]:
        pair_key = tuple(sorted([p1, p2]))
        candidates = [
            row for row in common_partners_df.iter_rows(named=True)
            if pair_key in [tuple(sorted(p)) for p in row['common_partners']] or 
               tuple(reversed(pair_key)) in [tuple(sorted(p)) for p in row['common_partners']]
        ]
        candidates = sorted(candidates, key=sort_key)
        
        assigned = None
        assigned_coach = None
        for row in candidates:
            assigned_coach = claim_coach(row['time_slot'], row['available_coaches'])
            if assigned_coach is not None:
                assigned = row
                break
        
        if assigned is None:
            has_coach = len(candidates) > 0 and any(len(c['available_coaches']) > 0 for c in candidates)
            reason = ('No coaches available in any viable time slot (slots lack coach coverage)'
                      if not has_coach else 'All coaches in viable slots already assigned')
            unassigned_pairs.append({
                'partner_1': p1, 'partner_2': p2,
                'discrepancy_score': pair_score_lookup[pair_key],
                'viable_time_slots': [r['time_slot'] for r in candidates],
                'reason': reason,
            })
        else:
            partner_rows.append({
                'time_slot': assigned['time_slot'], 'partner_1': p1, 'partner_2': p2,
                'discrepency_score': pair_score_lookup[pair_key], 'assigned_coach': assigned_coach,
            })
    
    # Assign coaches to individuals
    individual_ids = sorted({
        iid for row in common_partners_df.iter_rows(named=True)
        for iid in row.get('available_individuals', [])
    })
    
    for iid in individual_ids:
        candidates = [
            row for row in common_partners_df.iter_rows(named=True)
            if iid in row.get('available_individuals', [])
        ]
        candidates = sorted(candidates, key=sort_key)
        
        assigned = None
        assigned_coach = None
        for row in candidates:
            assigned_coach = claim_coach(row['time_slot'], row['available_coaches'])
            if assigned_coach is not None:
                assigned = row
                break
        
        if assigned is None:
            unassigned_individuals.append({
                'individual_id': iid,
                'viable_time_slots': [r['time_slot'] for r in candidates],
                'reason': 'No available coach in any viable time slot',
            })
        else:
            individual_rows.append({
                'time_slot': assigned['time_slot'], 'individual_id': iid, 'assigned_coach': assigned_coach,
            })
    
    return (pl.DataFrame(partner_rows), pl.DataFrame(individual_rows),
            pl.DataFrame(unassigned_pairs), pl.DataFrame(unassigned_individuals),
            session_counts, len(feasible_pairs))



def main(baseline: pl.DataFrame, coach: pl.DataFrame, seed: int):
    """Run the complete assignment analysis."""
    baseline_df, coach_df = load_data(baseline, coach)
    
    # Analyze coach availability
    coach_columns = [col for col in coach_df.columns if col != 'Initials']
    total_availability = sum(coach_df.filter(pl.col(col).cast(pl.Utf8) == '1').height for col in coach_columns)
    slots_with_coach = [col for col in coach_columns if coach_df.filter(pl.col(col).cast(pl.Utf8) == '1').height > 0]
    
    print("=" * 60)
    print("OPTIMIZED ASSIGNMENT ANALYSIS")
    print("=" * 60)
    print(f"\nTotal coach availability slots: {total_availability}")
    print(f"Time slots with coach coverage: {len(slots_with_coach)}")
    
    individuals_df, partner_df = setup_randomization(baseline_df, seed)
    print(f"\nPartner participants: {partner_df.height}")
    print(f"Individual participants: {individuals_df.height}")
    
    common_partners_df = get_common_partners_per_time(partner_df)
    common_partners_df = calculate_discrepency_score(partner_df, common_partners_df)
    common_partners_df = add_available_coaches(common_partners_df, coach_df)
    common_partners_df = add_available_individuals(common_partners_df, individuals_df)
    
    partner_assignments, individual_assignments, unassigned_pairs, unassigned_individuals, coach_counts, total_feasible = assign_participants(common_partners_df)
    
    print(f"\nTotal feasible pairs (with coach coverage): {total_feasible}")
    
    print("\n" + "=" * 60)
    print("ASSIGNMENT RESULTS")
    print("=" * 60)
    print(f"\nPartner pairs assigned: {len(partner_assignments)}")
    print(f"Individuals assigned: {len(individual_assignments)}")
    print(f"Total assigned: {len(partner_assignments) + len(individual_assignments)}")
    
    print(f"\n--- Unassigned Pairs ({len(unassigned_pairs)}) ---")
    for row in unassigned_pairs.iter_rows(named=True):
        print(f"  Pair ({row['partner_1']}, {row['partner_2']}): {row['reason']}")
        print(f"    Viable slots: {row['viable_time_slots']}")
    
    print(f"\n--- Unassigned Individuals ({len(unassigned_individuals)}) ---")
    for row in unassigned_individuals.iter_rows(named=True):
        print(f"  Individual {row['individual_id']}: {row['reason']}")
        print(f"    Viable slots: {row['viable_time_slots']}")
    
    print(f"\n--- Coach Workload Distribution ---")
    if coach_counts:
        for coach in sorted(coach_counts.keys()):
            print(f"  Coach {coach}: {coach_counts[coach]} sessions")
        avg = sum(coach_counts.values()) / len(coach_counts) if coach_counts else 0
        print(f"  Average per coach: {avg:.1f}")
    
    with Workbook('assignments_optimized_final.xlsx') as workbook:
        if len(partner_assignments) > 0:
            partner_assignments.write_excel(workbook=workbook, worksheet='Partner Assignments')
        if len(individual_assignments) > 0:
            individual_assignments.write_excel(workbook=workbook, worksheet='Individual Assignments')
        if len(unassigned_pairs) > 0:
            unassigned_pairs.write_excel(workbook=workbook, worksheet='Unassigned Pairs')
        if len(unassigned_individuals) > 0:
            unassigned_individuals.write_excel(workbook=workbook, worksheet='Unassigned Individuals')
    
    print(f"\nExported to assignments_optimized_final.xlsx")
    
    # Get where the Excel file is saved
    path = os.path.abspath('assignments_optimized_final.xlsx')
    return path


if __name__ == '__main__':
    main()