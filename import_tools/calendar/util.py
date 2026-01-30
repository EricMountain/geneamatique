"""
Utility module for calendar conversions between Gregorian and French Republican calendars.
"""

from datetime import date, timedelta


def gregorian_to_republican(g_year, g_month, g_day):
    """
    Convert a Gregorian date to French Republican date.

    Args:
        g_year (int): Gregorian year
        g_month (int): Gregorian month (1-12)
        g_day (int): Gregorian day (1-31)

    Returns:
        tuple: (republican_year, republican_month, republican_day)
               republican_month: 1-12 for regular months, 13 for complementary days
               republican_day: 1-30 for months 1-12, 1-5 or 1-6 for month 13

    Raises:
        ValueError: If the date is before September 22, 1792
    """
    start = date(1792, 9, 22)
    target = date(g_year, g_month, g_day)
    days_diff = (target - start).days

    if days_diff < 0:
        raise ValueError("Date before the start of the Republican calendar (September 22, 1792)")

    r_year = 1
    days_in_year = 365
    while days_diff >= days_in_year:
        days_diff -= days_in_year
        r_year += 1
        days_in_year = 366 if (r_year % 4 == 3) else 365

    if days_diff < 360:  # 12 months * 30 days
        r_month = days_diff // 30 + 1
        r_day = days_diff % 30 + 1
    else:
        r_month = 13  # Complementary days
        r_day = days_diff - 360 + 1

    return r_year, r_month, r_day


def republican_to_gregorian(r_year, r_month, r_day):
    """
    Convert a French Republican date to Gregorian date.

    Args:
        r_year (int): Republican year (1+)
        r_month (int): Republican month (1-12 for regular, 13 for complementary)
        r_day (int): Republican day (1-30 for months 1-12, 1-5/6 for month 13)

    Returns:
        tuple: (gregorian_year, gregorian_month, gregorian_day)

    Raises:
        ValueError: If inputs are invalid
    """
    if r_year < 1:
        raise ValueError("Republican year must be 1 or greater")
    if r_month < 1 or r_month > 13:
        raise ValueError("Republican month must be between 1 and 13")
    if r_month <= 12 and (r_day < 1 or r_day > 30):
        raise ValueError("Republican day must be between 1 and 30 for regular months")
    if r_month == 13:
        max_days = 6 if (r_year % 4 == 3) else 5
        if r_day < 1 or r_day > max_days:
            raise ValueError(f"Republican day must be between 1 and {max_days} for complementary days in year {r_year}")

    start = date(1792, 9, 22)
    days = 0
    for y in range(1, r_year):
        days += 366 if (y % 4 == 3) else 365

    if r_month <= 12:
        days += (r_month - 1) * 30 + (r_day - 1)
    else:
        days += 360 + (r_day - 1)

    result_date = start + timedelta(days=days)
    return result_date.year, result_date.month, result_date.day