"""Aggregates, GeoJSON and charts for the US Montessori private schools dataset.
Input : data/montessori_private_schools_1989_2024.csv (built by build_from_pss.py)
Output: data/*.csv, data/*.geojson, images/*.png
"""
import json, subprocess, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = f'{ROOT}/data'; IMG = f'{ROOT}/images'
GEO = os.environ.get('GEO_DIR', os.path.join(ROOT, 'scripts', 'geo'))      # us-atlas states + project.js (npm i us-atlas topojson-client d3-geo)
FONTS = os.environ.get('FONT_DIR', os.path.join(ROOT, 'scripts', 'fonts')) # Fraunces + DM Sans TTF
for f in os.listdir(FONTS):
    fm.fontManager.addfont(f'{FONTS}/{f}')
SERIF, SANS = 'Fraunces', 'DM Sans 9pt'
CREAM, INK, MUTED, GRID = '#F7F3EC', '#2B2A28', '#6B6862', '#E4DED3'
TC, BLUE, OLIVE = '#B4532F', '#1F72B8', '#7F9A1F'       # validated categorical order (AMS, AMI, other)
plt.rcParams.update({'font.family': SANS, 'font.size': 13, 'axes.edgecolor': GRID, 'axes.labelcolor': MUTED,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.facecolor': CREAM, 'figure.facecolor': CREAM,
                     'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True, 'grid.color': GRID,
                     'grid.linewidth': 0.8, 'axes.axisbelow': True})

s = pd.read_csv(f'{D}/montessori_private_schools_1989_2024.csv', low_memory=False,
                dtype={'school_id': str, 'zip5': str, 'county_fips': str})
tot = pd.read_csv(f'{D}/private_school_universe_totals.csv')
LATEST = '2023-24'
B = ['montessori_program_type', 'ams_member', 'ami_member', 'other_montessori_member', 'name_has_montessori']

# ---------- national series ----------
g = s.groupby(['survey_year', 'school_year_end'])
nat = pd.DataFrame({
    'montessori_schools': g.size(),
    'montessori_program_type': g.montessori_program_type.sum(),
    'ams_member': g.ams_member.sum(), 'ami_member': g.ami_member.sum(),
    'other_montessori_member': g.other_montessori_member.sum(), 'name_has_montessori': g.name_has_montessori.sum(),
    'weighted_estimate_program_type': s[s.montessori_program_type].groupby(['survey_year', 'school_year_end']).survey_weight.sum(min_count=1).round(),
    'students_k12': g.students_k12.sum(min_count=1), 'students_prek': g.students_prek.sum(min_count=1),
    'students_kindergarten': g.students_kindergarten.sum(min_count=1),
    'states_with_a_school': g.state.nunique(),
}).reset_index()
nat = nat.merge(tot[['survey_year', 'private_schools_in_file', 'private_schools_weighted']], on='survey_year', how='left')
nat['share_of_private_schools_pct'] = (100 * nat.montessori_schools / nat.private_schools_in_file).round(2)
nat.loc[nat.survey_year == '1993-94', 'private_schools_weighted'] = np.nan
for c in ['weighted_estimate_program_type', 'students_k12', 'students_prek', 'students_kindergarten', 'private_schools_weighted']:
    nat[c] = nat[c].astype('Int64')
nat.to_csv(f'{D}/national_by_year.csv', index=False)

# ---------- state x year ----------
st = s.groupby(['survey_year', 'school_year_end', 'state', 'state_name']).agg(
    montessori_schools=('school_id', 'size'), montessori_program_type=('montessori_program_type', 'sum'),
    ams_member=('ams_member', 'sum'), ami_member=('ami_member', 'sum'), other_montessori_member=('other_montessori_member', 'sum'),
    students_k12=('students_k12', 'sum'), students_prek=('students_prek', 'sum'), students_kindergarten=('students_kindergarten', 'sum'),
).reset_index()
st = st[st.state.ne('') & st.state.notna()]
st.to_csv(f'{D}/by_state_and_year.csv', index=False)

L = s[s.survey_year == LATEST].copy()
# ---------- state, latest, with rank and change since 2013-14 ----------
cur = st[st.survey_year == LATEST].set_index('state')
old = st[st.survey_year == '2013-14'].set_index('state')
sl = cur[['state_name', 'montessori_schools', 'ams_member', 'ami_member', 'students_k12', 'students_prek']].copy()
sl['schools_2013_14'] = old.montessori_schools.reindex(sl.index).fillna(0).astype(int)
sl['change_since_2013_14'] = sl.montessori_schools - sl.schools_2013_14
sl['share_of_us_montessori_pct'] = (100 * sl.montessori_schools / sl.montessori_schools.sum()).round(1)
sl = sl.sort_values('montessori_schools', ascending=False).reset_index()
sl.insert(0, 'rank', range(1, len(sl) + 1))
sl.to_csv(f'{D}/by_state_2023_24.csv', index=False)

# ---------- city, latest ----------
cy = L.groupby(['city', 'state']).agg(montessori_schools=('school_id', 'size'), ams_member=('ams_member', 'sum'),
                                      ami_member=('ami_member', 'sum'), students_k12=('students_k12', 'sum'),
                                      students_prek=('students_prek', 'sum'),
                                      latitude=('latitude', 'mean'), longitude=('longitude', 'mean')).reset_index()
cy['latitude'] = cy.latitude.round(4); cy['longitude'] = cy.longitude.round(4)
cy = cy.sort_values(['montessori_schools', 'students_k12'], ascending=False)
cy.to_csv(f'{D}/by_city_2023_24.csv', index=False)

# ---------- county, latest ----------
co = L[L.county_fips.notna()].groupby(['county_fips', 'state']).agg(montessori_schools=('school_id', 'size')).reset_index()
co.sort_values('montessori_schools', ascending=False).to_csv(f'{D}/by_county_2023_24.csv', index=False)

# ---------- locale x year ----------
lo = s[s.locale_group.notna() & s.locale_group.ne('')].groupby(['survey_year', 'locale_group']).size().unstack(fill_value=0)
lo = lo[[c for c in ['City', 'Suburb', 'Town', 'Rural'] if c in lo]].reset_index()
lo.to_csv(f'{D}/by_locale_and_year.csv', index=False)

# ---------- latest snapshot + GeoJSON ----------
keep = ['school_id', 'school_name', 'city', 'state', 'zip5', 'county_fips', 'latitude', 'longitude', 'locale_detail', 'program_type',
        'religious_typology', 'level', 'lowest_grade', 'highest_grade', 'students_k12', 'students_prek', 'students_kindergarten',
        'teachers_fte_k12'] + B
L[keep].sort_values(['state', 'city', 'school_name']).to_csv(f'{D}/montessori_private_schools_2023_24.csv', index=False)
feats = []
for r in L[keep].itertuples(index=False):
    r = r._asdict()
    if pd.isna(r['latitude']): continue
    props = {k: (None if (isinstance(v, float) and np.isnan(v)) else (bool(v) if isinstance(v, (np.bool_,)) else (int(v) if isinstance(v, (np.integer,)) else v)))
             for k, v in r.items() if k not in ('latitude', 'longitude')}
    feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(r['longitude'], 6), round(r['latitude'], 6)]}, 'properties': props})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(f'{D}/montessori_private_schools_2023_24.geojson', 'w'))

# ---------- charts ----------
def finish(fig, ax, title, sub, path, source=True):
    fig.text(0.06, 0.94, title, family=SERIF, weight=800, size=26, color=INK, va='top')
    fig.text(0.06, 0.875, sub, size=14, color=MUTED, va='top')
    if source:
        fig.text(0.06, 0.03, 'Source: NCES Private School Universe Survey, public-use files. Dataset by Montessori Theory (montessori-theory.com), CC BY 4.0.',
                 size=10.5, color=MUTED)
    fig.savefig(path, dpi=150); plt.close(fig)

# 1. national trend
fig = plt.figure(figsize=(12, 6.5)); ax = fig.add_axes([0.08, 0.13, 0.86, 0.66])
x = nat.school_year_end
ax.plot(x, nat.montessori_schools, color=TC, lw=2.4, marker='o', ms=6, mec=CREAM, mew=1.5, label='Any Montessori signal')
ax.plot(x, nat.montessori_program_type, color=BLUE, lw=2.4, marker='o', ms=6, mec=CREAM, mew=1.5, label='Type of school = Montessori')
ax.set_ylim(0, nat.montessori_schools.max() * 1.15); ax.set_xticks(x[::2]); ax.set_xticklabels(nat.survey_year[::2], rotation=0, size=11)
ax.annotate('Kindergarten-only schools are\nfirst coded in 1997-98', xy=(1998, nat.loc[nat.school_year_end == 1998, 'montessori_schools'].iloc[0]),
            xytext=(1999.5, 900), size=11, color=MUTED, arrowprops=dict(arrowstyle='-', color=MUTED, lw=0.8))
for name, col, yv in [('Any Montessori signal', TC, nat.montessori_schools.iloc[-1]), ('Type of school = Montessori', BLUE, nat.montessori_program_type.iloc[-1])]:
    ax.text(x.iloc[-1] + 0.4, yv, name, color=INK, size=11, va='center')
ax.set_xlim(x.min() - 1, x.max() + 7)
ax.set_ylabel('Schools in the file')
finish(fig, ax, 'Montessori private schools in the US, 1989-2024',
       f'{int(nat.montessori_schools.iloc[-1]):,} schools in 2023-24, counted in each NCES survey wave', f'{IMG}/national_trend.png')

# 2. top states
top = sl.head(15).iloc[::-1]
fig = plt.figure(figsize=(12, 7.5)); ax = fig.add_axes([0.2, 0.15, 0.72, 0.66])
ax.barh(top.state_name, top.montessori_schools, color=TC, height=0.68)
for yv, v in enumerate(top.montessori_schools):
    ax.text(v + 3, yv, f'{v}', va='center', size=11, color=INK)
ax.grid(axis='y', visible=False); ax.set_xlabel('Montessori private schools, 2023-24')
finish(fig, ax, 'Where the Montessori private schools are', 'The 15 states with the most schools in 2023-24', f'{IMG}/top_states_2023_24.png')

# 3. affiliations
fig = plt.figure(figsize=(12, 6.5)); ax = fig.add_axes([0.08, 0.13, 0.78, 0.66])
w = nat[nat.school_year_end >= 2006]
for col, c, lab in [('ams_member', TC, 'AMS member'), ('ami_member', BLUE, 'AMI member'), ('other_montessori_member', OLIVE, 'Other Montessori association')]:
    ax.plot(w.school_year_end, w[col], color=c, lw=2.4, marker='o', ms=6, mec=CREAM, mew=1.5)
    ax.text(w.school_year_end.iloc[-1] + 0.4, w[col].iloc[-1], lab, color=INK, size=11, va='center')
ax.set_xticks(w.school_year_end); ax.set_xticklabels(w.survey_year, size=11); ax.set_xlim(2005, 2029); ax.set_ylim(0, w.ams_member.max() * 1.2)
ax.set_ylabel('Schools reporting membership')
finish(fig, ax, 'Association membership, 2005-06 to 2023-24', 'A school can report more than one association. AMI is asked separately from 2005-06',
       f'{IMG}/associations.png')

# 4. map (latest)
def load_states():
    gj = json.load(open(f'{GEO}/states_albers.geojson'))
    polys = []
    for f in gj['features']:
        geom = f['geometry']; parts = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
        for p in parts:
            polys.append(Polygon(np.array(p[0]), closed=True))
    return polys

def project(df):
    pts = df[['longitude', 'latitude']].values.tolist()
    json.dump(pts, open('/tmp/pts.json', 'w'))
    subprocess.run(['node', f'{GEO}/project.js', '/tmp/pts.json', '/tmp/xy.json'], check=True, cwd=GEO)
    xy = json.load(open('/tmp/xy.json'))
    return np.array([p if p else [np.nan, np.nan] for p in xy])

xy = project(L)
def draw_map(ax, size=7, alpha=0.75):
    ax.add_collection(PatchCollection(load_states(), facecolor='#EFE8DC', edgecolor='#FFFFFF', lw=0.8))
    ax.scatter(xy[:, 0], xy[:, 1], s=size, color=TC, alpha=alpha, lw=0)
    ax.set_xlim(0, 975); ax.set_ylim(610, 0); ax.set_aspect('equal'); ax.axis('off')

fig = plt.figure(figsize=(12, 8)); ax = fig.add_axes([0.03, 0.06, 0.94, 0.78]); draw_map(ax)
finish(fig, ax, f'{len(L):,} Montessori private schools, 2023-24', 'One dot per school, from the coordinates published by NCES',
       f'{IMG}/map_2023_24.png')

# 5. cover 1600 x 800
fig = plt.figure(figsize=(16, 8), dpi=100)
ax = fig.add_axes([0.47, 0.08, 0.51, 0.84]); draw_map(ax, size=8, alpha=0.8)
fig.text(0.05, 0.80, 'US Montessori', family=SERIF, weight=800, size=54, color=TC, va='top')
fig.text(0.05, 0.67, 'Private Schools', family=SERIF, weight=800, size=54, color=TC, va='top')
fig.text(0.05, 0.53, '1989 to 2024', family=SERIF, weight=600, size=34, color=INK, va='top')
lines = [f'{len(s):,} school-year records, 18 NCES survey waves', f'{len(L):,} schools in 2023-24, by state, city and county',
         'AMS and AMI membership, enrollment, coordinates']
for i, t in enumerate(lines):
    fig.text(0.05, 0.40 - i * 0.065, t, size=18, color=INK, va='top')
fig.text(0.05, 0.08, 'Montessori Theory  ·  montessori-theory.com  ·  CC BY 4.0', size=15, color=MUTED, family=SERIF, weight=600)
fig.savefig(f'{IMG}/cover.png', dpi=100); plt.close(fig)

print(nat[['survey_year', 'montessori_schools', 'montessori_program_type', 'weighted_estimate_program_type', 'share_of_private_schools_pct']].to_string(index=False))
print(sl.head(10)[['rank', 'state', 'montessori_schools', 'change_since_2013_14']].to_string(index=False))
print('cities', len(cy), 'counties', len(co), 'geojson', len(feats))
