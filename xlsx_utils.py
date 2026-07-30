"""
XLSX Utilities for UCTalent Job Database.

Replaces CSV with beautifully formatted Excel spreadsheets.
All functions mirror the CSV DictReader/DictWriter interface
so the rest of the codebase doesn't need logic changes.

Features:
  - Bold, styled header row with blue background
  - Auto column widths (sensible caps per column type)
  - Wrap text on long content columns
  - Freeze top row + auto-filter
  - Priority-based row coloring (urgent = light red, normal = default)
"""

import os
import io
import re
from datetime import datetime

import openpyxl
from openpyxl import Workbook, load_workbook
from openpyxl.styles import (
    PatternFill, Font, Alignment, Border, Side, NamedStyle
)
from openpyxl.utils import get_column_letter

# ─── File Name ───────────────────────────────────────────────────────────────

XLSX_FILENAME = 'uctalent_jobs.xlsx'

WRAP_COLUMNS = {
    'description', 'boolean_query', 'outreach_message',
    'linkedin_post', 'x_post', 'facebook_post',
    'image_text', 'linkedin_comment', 'x_comment', 'facebook_comment',
    'linkedin_profiles', 'tags', 'title', 'referral_link', 'salary',
}

# These columns get extra width because they hold long text
WIDE_COLUMNS = {
    'description': 60,
    'outreach_message': 50,
    'linkedin_post': 55,
    'boolean_query': 55,
    'linkedin_profiles': 45,
}

# Columns that should be narrow
NARROW_COLUMNS = {
    'id': 28,
    'bounty': 10,
    'bounty_display': 18,
    'bounty_currency': 8,
    'priority': 10,
    'status': 14,
    'connect_status': 16,
    'message_status': 14,
    'created_at': 18,
    'last_updated': 18,
    'location': 28,
}

DEFAULT_COL_WIDTH = 22


# ─── Styles ──────────────────────────────────────────────────────────────────

HEADER_FILL = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
HEADER_FONT = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
HEADER_ALIGNMENT = Alignment(horizontal='center', vertical='center', wrap_text=True)

URGENT_FILL = PatternFill(start_color='FCE4D6', end_color='FCE4D6', fill_type='solid')  # light orange
URGENT_FONT = Font(name='Calibri', size=10, color='C65911')  # dark orange text

NORMAL_FILL = PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')  # light green
NORMAL_FONT = Font(name='Calibri', size=10, color='375623')  # dark green text

BODY_FONT = Font(name='Calibri', size=10)
BODY_ALIGNMENT = Alignment(vertical='top', wrap_text=True)
BODY_ALIGNMENT_NOWRAP = Alignment(vertical='top', wrap_text=False)

THIN_BORDER = Border(
    left=Side(style='thin', color='D9D9D9'),
    right=Side(style='thin', color='D9D9D9'),
    top=Side(style='thin', color='D9D9D9'),
    bottom=Side(style='thin', color='D9D9D9'),
)


# ─── Core Functions ──────────────────────────────────────────────────────────

def get_xlsx_path():
    """Return the canonical XLSX file path."""
    return XLSX_FILENAME


def read_xlsx(filepath=None):
    """Read XLSX file and return (list_of_dict_rows, fieldnames).
    
    Mirrors csv.DictReader interface.
    Returns ([], []) if file doesn't exist.
    """
    if filepath is None:
        filepath = XLSX_FILENAME
    
    if not os.path.exists(filepath):
        return [], []
    
    try:
        wb = load_workbook(filepath, data_only=True)
        ws = wb.active
        
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            wb.close()
            return [], []
        
        header = [str(cell).strip() if cell is not None else '' for cell in rows[0]]
        fieldnames = header
        
        result = []
        for row_values in rows[1:]:
            # Skip completely empty rows
            if all(v is None or (isinstance(v, str) and v.strip() == '') for v in row_values):
                continue
            
            row_dict = {}
            for i, field in enumerate(fieldnames):
                val = row_values[i] if i < len(row_values) else None
                if val is None:
                    val = ''
                elif not isinstance(val, str):
                    # Convert numbers/dates to string for consistency
                    if isinstance(val, datetime):
                        val = val.strftime('%Y-%m-%d %H:%M')
                    elif isinstance(val, (int, float)):
                        val = str(val)
                    else:
                        val = str(val)
                row_dict[field] = val.strip() if isinstance(val, str) else val
            
            result.append(row_dict)
        
        wb.close()
        return result, fieldnames
    
    except Exception as e:
        print(f"  ⚠️  Error reading XLSX: {e}")
        return [], []


def write_xlsx(filepath, rows, fieldnames):
    """Write rows to XLSX with formatting.
    
    Mirrors csv.DictWriter interface.
    Rows is a list of dicts, fieldnames defines column order.
    """
    if filepath is None:
        filepath = XLSX_FILENAME
    
    wb = Workbook()
    ws = wb.active
    ws.title = 'Jobs'
    
    # ── Write Header ──────────────────────────────────────────────────────
    for col_idx, field in enumerate(fieldnames, 1):
        cell = ws.cell(row=1, column=col_idx, value=field)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT
        cell.border = THIN_BORDER
    
    # ── Write Data ────────────────────────────────────────────────────────
    for row_idx, row_dict in enumerate(rows, 2):
        priority = str(row_dict.get('priority', '')).strip().lower()
        
        for col_idx, field in enumerate(fieldnames, 1):
            val = row_dict.get(field, '')
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            
            # Wrap text for long content columns
            if field in WRAP_COLUMNS:
                cell.alignment = BODY_ALIGNMENT
            else:
                cell.alignment = BODY_ALIGNMENT_NOWRAP
            
            # Priority-based row coloring
            if priority == 'urgent':
                cell.fill = URGENT_FILL
                cell.font = Font(name='Calibri', size=10, color='C65911')
            elif priority == 'normal':
                cell.fill = NORMAL_FILL
                cell.font = Font(name='Calibri', size=10, color='375623')
    
    # ── Column Widths ──────────────────────────────────────────────────────
    for col_idx, field in enumerate(fieldnames, 1):
        if field in WIDE_COLUMNS:
            ws.column_dimensions[get_column_letter(col_idx)].width = WIDE_COLUMNS[field]
        elif field in NARROW_COLUMNS:
            ws.column_dimensions[get_column_letter(col_idx)].width = NARROW_COLUMNS[field]
        else:
            # Auto-calculate based on content
            max_len = DEFAULT_COL_WIDTH
            for row_idx in range(1, len(rows) + 2):
                cell_val = ws.cell(row=row_idx, column=col_idx).value
                if cell_val:
                    # Approximate: count chars, cap at 45
                    length = min(len(str(cell_val)), 45)
                    if length > max_len:
                        max_len = length
            ws.column_dimensions[get_column_letter(col_idx)].width = max_len + 2
    
    # ── Freeze Panes & Auto-Filter ────────────────────────────────────────
    ws.freeze_panes = 'A2'
    last_col_letter = get_column_letter(len(fieldnames))
    ws.auto_filter.ref = f'A1:{last_col_letter}1'
    
    # ── Row Height for header ──────────────────────────────────────────────
    ws.row_dimensions[1].height = 30
    
    # ── Save ──────────────────────────────────────────────────────────────
    wb.save(filepath)
    wb.close()


def clear_xlsx(filepath, fieldnames):
    """Create a new empty XLSX with just the header row."""
    write_xlsx(filepath, [], fieldnames)


def migrate_csv_to_xlsx(csv_path='uctalent_jobs.csv', xlsx_path=None):
    """Migrate data from existing CSV to fresh XLSX.
    Returns (row_count, field_count) or (0,0) on failure.
    """
    if xlsx_path is None:
        xlsx_path = XLSX_FILENAME
    
    if not os.path.exists(csv_path):
        print(f"  ⚠️  No CSV found at {csv_path}, nothing to migrate.")
        return 0, 0
    
    import csv
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames
        
        if not fieldnames:
            print("  ⚠️  CSV has no headers, cannot migrate.")
            return 0, 0
        
        # Clean rows: ensure all keys exist
        cleaned = []
        for row in rows:
            clean_row = {}
            for fn in fieldnames:
                clean_row[fn] = row.get(fn, '')
            cleaned.append(clean_row)
        
        print(f"  📄 Read {len(cleaned)} rows from {csv_path}")
        write_xlsx(xlsx_path, cleaned, fieldnames)
        print(f"  ✅ Written to {xlsx_path}")
        return len(cleaned), len(fieldnames)
    
    except Exception as e:
        print(f"  ⚠️  Migration error: {e}")
        return 0, 0


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    # Fix console encoding for Windows (emoji & Unicode support)
    if hasattr(sys.stdout, 'reconfigure'):
        try: sys.stdout.reconfigure(encoding='utf-8')
        except: pass
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("XLSX Utils - UCTalent Job Database")
    print("=" * 60)
    
    action = sys.argv[1] if len(sys.argv) > 1 else 'migrate'
    
    if action == 'migrate':
        print("\n📋 Migrating CSV → XLSX...")
        count, fields = migrate_csv_to_xlsx()
        if count > 0:
            print(f"\n✅ Migration complete: {count} rows, {fields} columns")
            print(f"   File: {XLSX_FILENAME}")
        else:
            print("\n❌ Migration failed or nothing to migrate.")
    
    elif action == 'check':
        path = sys.argv[2] if len(sys.argv) > 2 else XLSX_FILENAME
        if os.path.exists(path):
            rows, fields = read_xlsx(path)
            print(f"\n📊 {path}:")
            print(f"   Rows: {len(rows)}")
            print(f"   Fields ({len(fields)}): {fields}")
            if rows:
                print(f"\n   Sample row:")
                for f in fields[:8]:
                    print(f"     {f}: {str(rows[0].get(f, ''))[:60]}")
        else:
            print(f"\n❌ File not found: {path}")
    
    elif action == 'clear':
        path = sys.argv[2] if len(sys.argv) > 2 else XLSX_FILENAME
        from linkedin_outreach import CSV_FIELDNAMES
        confirm = input(f"\n  ⚠️  Clear ALL data in {path}? (y/n): ").strip().lower()
        if confirm == 'y':
            clear_xlsx(path, CSV_FIELDNAMES)
            print(f"  ✅ {path} cleared (header only)")
        else:
            print("  Skipped.")
    
    else:
        print("Usage:")
        print("  python xlsx_utils.py migrate   - Migrate CSV → XLSX")
        print("  python xlsx_utils.py check     - Check XLSX contents")
        print("  python xlsx_utils.py clear     - Clear XLSX (header only)")
