# import historical_data

# def calculate_expected_points(player_name):
#     # Read the historical data from the file
#     data = historical_data.load_data()

#     # Find the player's past performance
#     player_data = data.get(player_name, [])

#     # Calculate the average points scored by the player
#     total_points = sum(player_data)
#     average_points = total_points / len(player_data) if len(player_data) > 0 else 0

#     # Return the estimated expected points for the player in their next game
#     return average_points

# # Example usage
# player_name = "John Doe"
# expected_points = calculate_expected_points(player_name)
# print(f"Expected points for {player_name} in the next game: {expected_points}")




############################ GPT ANSWER###########################

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import numpy as np

# Example DataFrame
team_data = pd.read_csv('')  # Assuming you have your data in a CSV file

# Splitting the data into features and target
X = team_data[['team_offensive_ability', 'opponent_defensive_ability']]
y = team_data['actual_points_scored']

# Splitting data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

# Creating and training the model
model = LinearRegression()
model.fit(X_train, y_train)

# Making predictions and evaluating the model
predictions = model.predict(X_test)
mse = mean_squared_error(y_test, predictions)
print(f"Mean Squared Error: {mse}")

# Predicting for an upcoming game
upcoming_game_features = np.array([[team_offensive_rating, opponent_defensive_rating]])  # Replace with actual ratings
predicted_points = model.predict(upcoming_game_features)
print(f"Predicted Points for the Upcoming Game: {predicted_points[0]}")
