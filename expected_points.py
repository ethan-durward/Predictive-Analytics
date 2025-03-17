import json
import pandas as pd
from sklearn.linear_model import LinearRegression
import statsmodels.api as sm

# Load player stats and team ratings
with open('./JSON/detailed_player_stats.json', 'r') as f:
    player_stats = json.load(f)

with open('./JSON/nba_player_short.json', 'r') as f:
    player_info = json.load(f)

with open('./JSON/team_ratings.json', 'r') as f:
    team_ratings = json.load(f)




# Convert player stats to a DataFrame
stats_df = pd.DataFrame(player_stats)

# Join player stats with player info
stats_df = stats_df.merge(pd.DataFrame(player_info), left_on='Player_ID', right_on='id')

# Feature engineering: Compute defensive rating of the opponent team
stats_df['Opponent_DEF_Rating'] = stats_df['MATCHUP'].apply(lambda x: team_ratings[x.split()[-1]]['def'])

# Prepare data for regression
X = stats_df[['FGA', 'FG_PCT', 'FG3A', 'FG3_PCT', 'FTA', 'FT_PCT', 'Opponent_DEF_Rating']]
y = stats_df['PTS']
# deleted OREB, DREB, STL, BLK, TOV from the features list

# Train a linear regression model
model = LinearRegression()
model.fit(X, y)

## Testing the model and its related values ##
X = sm.add_constant(X)
model = sm.OLS(y, X).fit()
print(model.summary())


# Function to estimate points for a given player and opponent
def estimate_points(player_id, opponent_def_rating, past_stats):
    player_stats = stats_df[stats_df["Player_ID"] == player_id]
    player_stats = player_stats[['FGA', 'FG_PCT', 'FG3A', 'FG3_PCT', 'FTA', 'FT_PCT', 'Opponent_DEF_Rating']]
    # player_stats = player_stats.rolling(window=past_stats).mean().dropna()
    
    if not player_stats.empty: 
        features = player_stats.iloc[-1].tolist() + [opponent_def_rating]
        predicted_points = model.predict([features])[0]
        return predicted_points
    else:
        print(f"No recent stats found for player ID: {player_id}") 
        return -1000
    
    ## Old Code ##
    # [fga, fg_pct, fg3a, fg3_pct, fta, ft_pct, opponent_def_rating]
    # return model.predict([features])[0]



# Example usage
giannis_id = 203507
opponent_def_rating = 113.8  # Example: Milwaukee's defensive rating
estimated_points = estimate_points(giannis_id, opponent_def_rating, 140)
print(f"Estimated points for Giannis against Milwaukee: {estimated_points:.2f}")