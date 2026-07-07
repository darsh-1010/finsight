import React from 'react';

const Loader: React.FC = () => (
  <div className="flex-1 flex justify-center items-center w-full h-full min-h-[50vh] bg-background">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
  </div>
);

export default Loader;
