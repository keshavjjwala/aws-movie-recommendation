# Movie Picks — Movie Recommendation System on AWS

A personalized movie discovery platform that helps users find movies they love, discover similar titles, receive recommendations based on their preferences, and manage their personal watchlist.

**Live Demo:** [Open Movie Picks](http://movie-recommender-frontendbucket-dic5xttnloqu.s3-website-us-east-1.amazonaws.com)

**Repository:** [aws-movie-recommendation](https://github.com/keshavjjwala/aws-movie-recommendation)

## Overview

Movie Picks is a full-stack movie recommendation application built with Python, machine learning, and AWS. It combines content-based filtering with collaborative filtering to generate personalized movie recommendations.

Users can create an account, explore movies, rate titles, maintain a watchlist, and discover recommendations based on their interests and activity.

The application uses a serverless AWS architecture for its backend, with Amazon S3 hosting the frontend and storing the recommendation model.

## Features

- **Personalized Recommendations:** Discover movies based on preferences and viewing activity.
- **Movie Search:** Search for movies by title.
- **Movie Details:** Explore posters, plot summaries, cast, directors, ratings, and other available metadata.
- **Similar Movies:** Find titles related to a selected movie.
- **Personal Watchlist:** Track movies you plan to watch, are watching, have watched, or have dropped.
- **Movie Ratings:** Rate movies and use your preferences to improve recommendations.
- **User Authentication:** Sign up and sign in using Amazon Cognito in the AWS deployment.
- **Personal Statistics:** View watchlist statistics, average ratings, time watched, and favourite genres.
- **Cloud Deployment:** Host the application using AWS managed and serverless services.

## Technology Stack

| Category | Technologies |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| Machine Learning | Content-based filtering, collaborative filtering |
| Authentication | Amazon Cognito |
| API | Amazon API Gateway, AWS Lambda |
| Database | Amazon DynamoDB |
| Object Storage | Amazon S3 |
| Infrastructure as Code | AWS SAM, AWS CloudFormation |
| Local Development | Docker, DynamoDB Local |
| Testing | pytest |
| Data Sources | MovieLens, TMDB |

## AWS Architecture

The application uses the following AWS services:

- **Amazon S3:** Hosts the static frontend and stores the recommendation model.
- **AWS Lambda:** Executes the Python API without requiring a continuously running application server.
- **Amazon API Gateway:** Exposes HTTP endpoints and routes requests to Lambda.
- **Amazon Cognito:** Manages user authentication and issues tokens for protected API requests.
- **Amazon DynamoDB:** Stores users' movie-library data.
- **AWS IAM:** Controls permissions for interactions between AWS services.
- **AWS SAM and CloudFormation:** Define, deploy, and manage the cloud infrastructure as code.

### Request Flow

1. A user opens the Movie Picks website.
2. The frontend sends requests to the API Gateway endpoint.
3. Public endpoints handle movie discovery, while protected endpoints require valid authentication.
4. API Gateway invokes the Python backend through Lambda.
5. The backend loads the recommendation model from S3 and accesses DynamoDB when user-specific data is needed.
6. The API returns results to the frontend for display.

## Recommendation Engine

Movie Picks combines content-based and collaborative filtering techniques to generate recommendations.

- **Content-based filtering** uses movie characteristics and similarity to identify related titles.
- **Collaborative filtering** uses preference and rating patterns to support personalized recommendations.
- **User activity** helps the application tailor recommendations and maintain a personal movie library.

The model is prepared offline and stored as a compressed JSON artifact. The deployed backend loads the model for inference.

## Getting Started

### Prerequisites

- Python 3.12 or later
- Docker Desktop
- Git
- AWS CLI and AWS SAM CLI for cloud deployment

### 1. Clone the repository

```bash
git clone https://github.com/keshavjjwala/aws-movie-recommendation.git
cd aws-movie-recommendation
```

### 2. Install development dependencies

Create and activate a virtual environment.

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

**macOS / Linux**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 3. Prepare the recommendation model

```bash
python train.py
```

This downloads the MovieLens dataset and generates the model artifact at `model/model.json.gz`.

### 4. Start the local application

```bash
./scripts/run-local.sh
```

On Windows, use the repository's provided PowerShell-compatible workflow or run the required commands through Git Bash/WSL.

The local setup uses Docker to run DynamoDB Local and provides a local authentication mechanism for development.

Open:

```text
http://localhost:8000
```

Create a local account and start exploring movies.

### Optional: Enrich movie metadata

To fetch additional posters, plots, and cast information, configure a TMDB API key in your local `.env` file using `.env.example` as a template. Then run:

```bash
python enrich.py
python train.py
```

The TMDB key is used by the local enrichment script. Never commit API keys or credentials to GitHub.

## Deploying to AWS

The project includes an AWS SAM template that defines the application infrastructure.

For a standard AWS account, configure the AWS CLI and SAM CLI, then follow the deployment instructions in [`docs/deploy-aws.md`](docs/deploy-aws.md).

The repository includes deployment scripts:

```bash
./scripts/deploy.sh
```

To remove the deployed application when it is no longer needed:

```bash
./scripts/destroy.sh
```

**AWS Academy Learner Lab:** Lab accounts may restrict IAM role creation and certain AWS services. The deployment template and configuration may need to use the existing `LabRole`. Follow the repository's deployment guide and your lab's restrictions.

> **Important:** The destroy script removes deployed resources and can delete user accounts and application data. Review its effects before running it.

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/movies/search?q=matrix` | Search movies by title |
| GET | `/api/movies/popular` | Retrieve popular movies |
| GET | `/api/movies/{id}` | Get movie details |
| GET | `/api/movies/{id}/similar` | Find similar movies |
| GET | `/api/me/library` | Retrieve the user's movie library |
| PUT | `/api/me/library/{id}/status` | Update a movie's watch status |
| PUT | `/api/me/library/{id}/rating` | Rate a movie |
| DELETE | `/api/me/library/{id}/rating` | Remove a movie rating |
| DELETE | `/api/me/library/{id}` | Remove a movie from the library |
| GET | `/api/me/recommendations` | Retrieve personalized recommendations |
| GET | `/api/me/stats` | Retrieve personal viewing statistics |

Protected `/api/me/*` endpoints require a bearer token. The AWS deployment uses Cognito authentication; local development uses the local authentication mechanism.

## Testing

Run the automated test suite with:

```bash
pytest
```

The tests cover recommendation logic, model preparation, movie-library storage, authentication, API behavior, and Lambda request handling.

## Project Structure

```text
aws-movie-recommendation/
├── app/
│   ├── auth.py
│   ├── library.py
│   ├── main.py
│   ├── model_loader.py
│   ├── recommender.py
│   ├── server.py
│   └── storage.py
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── js/
│       ├── api.js
│       ├── auth.js
│       ├── library.js
│       └── views/
├── docs/
├── scripts/
├── tests/
├── model/
├── template.yaml
├── train.py
├── enrich.py
├── requirements.txt
├── requirements-dev.txt
├── docker-compose.yml
└── README.md
```

## Data Sources and Acknowledgements

- **MovieLens:** Movie ratings and dataset information from GroupLens Research.
- **TMDB:** Movie metadata and imagery through The Movie Database API.

This product uses the TMDB API but is not endorsed or certified by TMDB. Review the respective data-source terms before redistributing data or imagery.

## Future Improvements

Potential areas for further development include:

- Improved recommendation evaluation and ranking.
- More detailed application monitoring and performance metrics.
- Enhanced accessibility and responsive design.
- Automated deployment and testing workflows.
- Additional AWS security and observability improvements.

## Author

**Keshav Jhunjhunwala**

Computer Science and Engineering student interested in cloud computing, machine learning, and full-stack development.

- GitHub: [@keshavjjwala](https://github.com/keshavjjwala)
- Project: [Movie Picks](https://github.com/keshavjjwala/aws-movie-recommendation)
