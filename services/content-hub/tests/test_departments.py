def test_list_departments_for_authenticated_user(auth_client):
    response = auth_client.get("/api/departments")
    assert response.status_code == 200
    departments = response.json()["departments"]
    assert len(departments) >= 5
    assert any(department["code"] == "marketing" for department in departments)


def test_it_master_can_create_and_assign_department(it_auth_client):
    create = it_auth_client.post(
        "/api/departments",
        json={"name": "Forschung", "code": "research", "sort_order": 60},
    )
    assert create.status_code == 200
    department_id = create.json()["department"]["id"]

    users = it_auth_client.get("/api/user/users").json()["users"]
    target = users[0]

    assign = it_auth_client.patch(
        f"/api/user/users/{target['db_id']}/department",
        json={"department_id": department_id},
    )
    assert assign.status_code == 200
    assert assign.json()["user"]["department_id"] == department_id
    assert assign.json()["user"]["department_name"] == "Forschung"


def test_it_master_can_create_user_with_password(it_auth_client):
    create = it_auth_client.post(
        "/api/user/users",
        json={
            "email": "employee@carbonauten.com",
            "name": "Employee One",
            "password": "employee-password",
            "role": "editor",
        },
    )
    assert create.status_code == 200

    login = it_auth_client.post(
        "/api/auth/login",
        json={"email": "employee@carbonauten.com", "password": "employee-password"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "editor"


def test_editor_cannot_create_department(auth_client):
    response = auth_client.post(
        "/api/departments",
        json={"name": "Blocked", "code": "blocked"},
    )
    assert response.status_code == 403


def test_it_master_can_delete_department(it_auth_client):
    create = it_auth_client.post(
        "/api/departments",
        json={"name": "Temp", "code": "temp-dept"},
    )
    department_id = create.json()["department"]["id"]
    delete = it_auth_client.delete(f"/api/departments/{department_id}")
    assert delete.status_code == 200
    listing = it_auth_client.get("/api/departments?include_inactive=true")
    assert all(department["id"] != department_id for department in listing.json()["departments"])
