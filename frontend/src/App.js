import React from 'react';
import React from 'react'; // Ensure React is imported for useState, useEffect
import { Admin, Resource, CustomRoutes, Authenticated } from 'react-admin';
import { Route } from 'react-router-dom'; // For CustomRoutes
import dataProvider from './dataProvider';
import authProvider from './authProvider';
import Dashboard from './Dashboard'; // Assuming Dashboard can be generic or also conditional
import { UserList, UserEdit, UserCreate } from './resources/users';
import { AttendanceList } from './resources/attendance';
import { LessonList } from './resources/lessons/LessonList';
import { LessonCreate } from './resources/lessons/LessonCreate';
import { LessonEdit } from './resources/lessons/LessonEdit';
import { StudentLessonList } from './resources/student/StudentLessonList';
import { StudentLessonView } from './resources/student/StudentLessonView';
import { FaceRegistrationPage } from './resources/student/FaceRegistrationPage'; // Added import

export default function App() {
  const [permissions, setPermissions] = React.useState(null);
  const [loadingPermissions, setLoadingPermissions] = React.useState(true);


  React.useEffect(() => {
    if (authProvider && authProvider.getPermissions) {
      authProvider.getPermissions()
        .then(perms => {
          setPermissions(perms);
          setLoadingPermissions(false);
        })
        .catch(() => {
          setPermissions(null); // Or some default/error state
          setLoadingPermissions(false);
        });
    } else {
      setLoadingPermissions(false); // No authProvider.getPermissions, proceed without specific role
      setPermissions('teacher'); // Default to teacher if no specific permissions logic, or handle appropriately
    }
  }, []);

  // Show a loading screen or similar while permissions are being determined
  if (loadingPermissions) {
    return <div>Loading permissions...</div>; // Or your app's loading component
  }

  return (
    <Admin dashboard={Dashboard} dataProvider={dataProvider} authProvider={authProvider}>
      {permissions === 'teacher' && (
        <>
          <Resource name="users" list={UserList} edit={UserEdit} create={UserCreate} />
          <Resource name="lessons" list={LessonList} create={LessonCreate} edit={LessonEdit} />
          <Resource name="attendance" list={AttendanceList} />
          {/* Dummy resources for ReferenceManyField and DeleteButton if they rely on resource definitions */}
          <Resource name="lessonfiles" /> 
          <Resource name="studentlessonenrollments" />
          <Resource name="files" />
        </>
      )}
      {permissions === 'student' && (
        <CustomRoutes>
          <Route 
            path="/student/lessons" 
            element={
              <Authenticated>
                <StudentLessonList />
              </Authenticated>
            } 
          />
          <Route 
            path="/student/lessons/:lessonId" 
            element={
              <Authenticated>
                <StudentLessonView />
              </Authenticated>
            } 
          />
          {/* Optional: Redirect to /student/lessons if student lands on root */}
           <Route 
            path="/" 
            element={
              <Authenticated>
                <StudentLessonList /> 
              </Authenticated>
            } 
          />
          <Route 
            path="/student/register-face" 
            element={
              <Authenticated>
                <FaceRegistrationPage />
              </Authenticated>
            } 
          />
        </CustomRoutes>
      )}
      {/* Fallback for users with no specific role or if permissions is null */}
      {/* This part might need adjustment based on how unauthenticated/unauthorized users should be handled */}
      {/* For example, if permissions are null, they might be redirected to login or a generic page */}
      {(!permissions || (permissions !== 'teacher' && permissions !== 'student')) && (
         <CustomRoutes>
            <Route path="/" element={<Dashboard />} /> 
            {/* Or a message like "No resources available for your role." */}
            {/* Or redirect to login if not authenticated by authProvider */}
         </CustomRoutes>
      )}
    </Admin>
  );
}