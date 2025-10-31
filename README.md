# Template for a flask restful api

This template is a starting point for building a flask restful api using flask-restx and flask-sqlalchemy.


## Project Setup

To use the template, you need to clone the repository and follow these steps to set up and run the project on your local machine.

### 1. Clone the Repository

Create an empty directory on your local machine and clone the repository into the directory.

```bash
cd project-name
git clone https://github.com/QENEST/flask_restx_api_template.git
```

### 2. Set up a Virtual Environment

#### Create Virtual Environment
```bash
python3 -m venv venv 
```

#### Activate Virtual Environment
```bash
source venv/bin/activate
```

#### Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up the Database

#### Create the Database
Create a local database to be used by the application in development. 
You can use any database of your choice.

### 4. Set up configurations
- In the `extensions.py` file, edit the `api_prefix` and `api_version`.
- In the __init__.py file, edit the `api_title` and `api_description`.

- Create an instance folder in the root directory of the project and create a `config.py` file in the instance folder.
Use the recommended template for the config file to set up the configurations.

- Specifically, you need to set up the following configurations:

```
CONNECTIONS
MYSQL_CONNECTIONS
NO_SSH_CONNECTION
```

- Note the use API_KEY authentication for the api. Ensure you create a user with an api_key to access protected resources.

### 5. Run the Application

Run the application using the command below:

```bash
python3 application.py
```
You should see the application running on `http://localhost:5000/`

### 6. Test the Application
The application provides a swagger documentation that can be used to test the api endpoints.




