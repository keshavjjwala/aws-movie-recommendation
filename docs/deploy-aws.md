# Deploying to AWS

One script creates and connects everything. You don't click anything together in the AWS console; the console is only for checking what got made (and for showing it off).

Time: about 30 minutes the first time, mostly installing tools. Cost: nothing noticeable for a demo; it all fits in the free tier, and credits cover anything beyond.

## 1. One-time setup in the AWS console

1. **Sign in** to <https://console.aws.amazon.com> with the account that has the credits.
2. **Set a budget alarm** so credits can't quietly drain: search "Budgets" → *Create budget* → *Use a template* → *Zero spend budget* (or a monthly budget of $5) → enter your email → *Create*.
3. **Create a user for the command line.** Don't use the root login for this.
   - Search "IAM" → *Users* → *Create user*, name it `deployer`.
   - *Attach policies directly* → tick **AdministratorAccess** → *Create user*.
   - Open the user → *Security credentials* → *Create access key* → *Command Line Interface (CLI)* → tick the confirmation → *Create*.
   - Copy the **Access key ID** and **Secret access key** now; the secret is only shown once. Never commit them to git.
4. **Pick a region** and stick to it, e.g. `ap-south-1` (Mumbai) or `us-east-1` (N. Virginia). Every service used here exists in both. When you look for things in the console later, check the region picker (top right) matches.

## 2. Install the tools on your laptop

| Tool | Why | Install |
|---|---|---|
| AWS CLI v2 | Talks to your account | <https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html> |
| AWS SAM CLI | Turns `template.yaml` into AWS resources | <https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html> |
| Docker | Builds the Lambda package if you don't have Python 3.12 | Already needed for running locally |
| Python 3.12+ | Training the model | Already needed for running locally |

Then connect the CLI to your account:

```bash
aws configure
# AWS Access Key ID:     <from step 1.3>
# AWS Secret Access Key: <from step 1.3>
# Default region name:   ap-south-1        (your region from step 1.4)
# Default output format: json

aws sts get-caller-identity   # should print your account id and user/deployer
```

## 3. Build the model

From the project folder, with the virtualenv active (see the README):

```bash
python enrich.py   # optional but recommended: real posters, plots and cast (needs the TMDB key in .env)
python train.py    # writes model/model.json.gz
```

If you skip this, `deploy.sh` runs `train.py` for you, but the site will show generated posters instead of real ones. To add posters later, run both commands and deploy again.

## 4. Deploy

```bash
./scripts/deploy.sh
```

It takes 3–5 minutes and ends with:

```
API:     https://abc123.execute-api.ap-south-1.amazonaws.com
Website: http://movie-recommender-frontendbucket-xyz.s3-website.ap-south-1.amazonaws.com
```

Open the **Website** link, create an account with a real email, enter the 6-digit code (from `no-reply@verificationemail.com`; check spam) and you're in.

Changed the code or retrained the model? Run `./scripts/deploy.sh` again; it only updates what changed.

## What the script does, and how everything is connected

`deploy.sh` does four things:

1. Copies `app/` and `requirements.txt` into `build/lambda-src/` (the Lambda package).
2. `sam build` + `sam deploy`: SAM reads `template.yaml` and asks **CloudFormation** to create every resource below as one *stack* called `movie-recommender`. CloudFormation also wires them together.
3. Uploads `model/model.json.gz` to the model bucket.
4. Writes `config.js` with the API URL and Cognito ids, then uploads the website to the website bucket.

What gets created (look them up in the console in your region):

| Console | Resource | Connected to |
|---|---|---|
| **S3** | Website bucket (public, static website hosting) | Serves `index.html`, CSS, JS. Its `config.js` holds the API URL and the Cognito app client id, so the browser knows where to go. |
| **Cognito** → User pools | User pool (email = username, code verification) + app client `UserPoolClient` | The browser calls it directly to sign up, confirm and sign in, and gets back an ID token. Accounts show up under *Users*. |
| **API Gateway** | HTTP API with a *JWT authorizer* | The authorizer is pointed at the user pool (issuer) and the app client (audience). Routes: `/api/me/*` require a valid token; everything else is public. Every route forwards to the Lambda. |
| **Lambda** | `ApiFunction` (Python 3.12, FastAPI + Mangum) | Triggered by API Gateway. Environment variables tell it the table name and model bucket. Reads the user id from the token claims API Gateway already checked. |
| **DynamoDB** | Library table (`userId` + `movieId`) | The Lambda reads and writes each user's list here. Open the table → *Explore items* to see lists appear as people use the site. |
| **S3** | Model bucket (private) | The Lambda downloads `model.json.gz` once per cold start. |
| **IAM** → Roles | The Lambda's role | Allows exactly: read/write the Library table, read the model bucket, write logs. Nothing else. |
| **CloudWatch** → Log groups | `/aws/lambda/movie-recommender-ApiFunction-…` | Every Lambda request and error. First place to look when something breaks. |
| **CloudFormation** → Stacks | `movie-recommender` | The whole set above. *Resources* tab lists everything; *Outputs* tab has the URLs. |

The request path, once deployed:

```
Browser ── loads page ──────────────────────────────▶ S3 website bucket
Browser ── sign up / sign in ───────────────────────▶ Cognito  ──▶ ID token
Browser ── /api/me/... + "Authorization: Bearer <token>" ─▶ API Gateway
                                                            │ checks the token against Cognito
                                                            ▼
                                                          Lambda ──▶ DynamoDB (lists)
                                                                 └─▶ S3 model bucket
```

`docs/architecture.md` has the full diagram and the reasoning behind each choice.

## 5. Delete everything when you're done

```bash
./scripts/destroy.sh
```

This empties both buckets and deletes the stack: every resource above, including all accounts and lists. Also delete the `deployer` access key in IAM if you won't deploy again. SAM leaves one small bucket named `aws-sam-cli-managed-default-…` holding upload artifacts; it costs almost nothing, and you can empty and delete it in S3 (and its stack `aws-sam-cli-managed-default` in CloudFormation) if you want a clean account.

## When something goes wrong

| Symptom | Fix |
|---|---|
| `Unable to locate credentials` / `ExpiredToken` | Run `aws configure` again; check with `aws sts get-caller-identity`. |
| `sam: command not found` | Install the SAM CLI (step 2) and open a new terminal. |
| `sam build` fails with a Docker error | Docker isn't running. Start it, or install Python 3.12 so SAM builds without Docker. |
| Stack fails on `FrontendBucketPolicy` with *AccessDenied* / *public policies are blocked* | The account blocks public buckets account-wide. S3 → *Block Public Access settings for this account* → *Edit* → untick *Block public access to buckets and objects granted through new public bucket policies* and *…any public bucket policies* → save, then run `deploy.sh` again. If CloudFormation says the stack is in `ROLLBACK_COMPLETE`, run `./scripts/destroy.sh` first. |
| Website loads but movies show "The server rejected the request (500)" | The Lambda crashed: open its CloudWatch log group and read the newest error. If it says the model is missing, run `deploy.sh` again (it uploads the model). |
| "Can't reach the server" | `config.js` points at an API that no longer exists, usually after destroying and redeploying. Run `deploy.sh` again and hard-refresh the page. |
| No verification email | Check spam. Cognito's built-in sender allows about 50 emails a day per account; if you hit that, wait a day. In an emergency, confirm a user by hand: Cognito → User pool → *Users* → pick the user → *Actions* → *Confirm account*. |
| "Your session has ended. Sign in again." right after signing in | API Gateway rejected the token, usually a tab left open from an older stack. Sign in again; if it keeps happening, check the authorizer in API Gateway points at the current user pool. |
